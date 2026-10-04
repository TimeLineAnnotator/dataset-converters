import csv
import json
import subprocess
import sys
import zipfile
from fractions import Fraction
from pathlib import Path

import pytest

from bpsd import convert
from bpsd.bars import Bar, align

CONVERT = Path(convert.__file__)
FIXTURES = ["Op002No1-01_AB96", "Op002No1-01_AS35"]


def rows(text):
    return list(csv.DictReader(text.strip().splitlines(), delimiter=";"))


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------- without the archive
def test_352_items():
    assert len(convert.ITEMS) == 352 == len(set(convert.ITEMS))
    assert "Op031No3-01_FG67" in convert.ITEMS


@pytest.mark.parametrize("piece, title", [
    ("Op002No1-01", "Piano Sonata Op. 2 No. 1, i"),
    ("Op007-01", "Piano Sonata Op. 7, i"),
    ("Op081a-01", "Piano Sonata Op. 81a, i"),
    ("Op106-01", "Piano Sonata Op. 106, i"),
])
def test_titles(piece, title):
    assert convert.piece_title(piece) == title


def test_checksums_cover_every_member_read():
    sums = json.loads(convert.CHECKSUMS.read_text())
    assert set(convert.checksum_members()) == set(sums)


def test_measure_rows_pickup_partial_end_and_repeat():
    # unfolded bars 0 (pickup), 1, 2, 3, 4; bar 3 and 4 repeat printed bars 1 and 2; the end is a partial bar
    numbers = (0, 1, 2, 1, 2)
    source = rows("time;measure\n1.0;0.750\n2.0;1.000\n3.0;2.000\n4.0;3.000\n5.0;4.000\n6.0;4.250")
    out = convert.measure_rows(source, numbers, pickup=True)
    assert [r["measure"] for r in out] == [0, 1, 2, 1, 2, 3]
    assert {r["is_first_in_measure"] for r in out} == {"true"}
    assert [r["time"] for r in out] == ["1.0", "2.0", "3.0", "4.0", "5.0", "6.0"]


def test_measure_rows_end_on_a_bar_line_without_pickup():
    source = rows("time;measure\n0.5;1.000\n1.5;2.000\n2.5;3.000")
    out = convert.measure_rows(source, (1, 2), pickup=False)
    assert [r["measure"] for r in out] == [1, 2, 3]


def test_structure_levels_and_duplicates():
    fine = rows("start;end;structure\n0.0;1.0;Exposition:FirstGroup\n0.0;1.0;Exposition:FirstGroup\n"
                "1.0;3.0;Development")
    coarse = rows("start;end;structure\n0.0;1.0;Exposition\n1.0;3.0;Development\n1.0;3.0;Development")
    out = convert.structure_rows(fine, coarse)
    assert len(out) == 4
    assert [(r["level"], r["label"]) for r in out] == [
        (2, "Exposition"), (1, "FirstGroup"), (2, "Development"), (1, "Development")]


def test_write_script_is_the_one_place_for_commands(tmp_path):
    csvs = {k: tmp_path / f"{k}.csv" for k in ("measures", "structure", "harmony", "unparsed")}
    text = convert.write_script("X_AB96", csvs, tmp_path / "x.tla", {"title": "T"}, media_length=12.5)
    lines = text.splitlines()
    assert lines[0] == 'metadata set "title" "T"'
    assert "metadata set-media-length 12.5" in lines
    assert not any(l.startswith("load-media") for l in lines)
    assert all("by-measure" not in l for l in lines)
    assert lines[-1] == f"save {tmp_path / 'x.tla'} --overwrite"
    with_media = convert.write_script("X_AS35", csvs, tmp_path / "x.tla", {}, media=tmp_path / "a.wav")
    assert f"load-media {tmp_path / 'a.wav'}" in with_media.splitlines()


def test_alignment_unfolds_a_repeat_and_a_split_bar():
    def bar(number, pitch, length=4, repeat_end=False, repeat_start=False):
        notes = ((Fraction(0), Fraction(length), "1", "1", ("C", "0", str(pitch))),)
        return Bar(str(number), notes, Fraction(length), Fraction(4), repeat_end, repeat_start)

    # printed: pickup (1 beat), bars 1-3 (printed 2-4), a 3-beat bar closing a repeat, its 1-beat tail, a last bar
    printed = [bar(1, 1, 1), bar(2, 2), bar(3, 3), bar(4, 4, 3, repeat_end=True), bar(5, 5, 1), bar(6, 6)]
    # unfolded: pickup, 1, 2, bar 4 + pickup (merged), 1, 2, bar 4 + tail (merged), bar 6
    def merged(a, b):
        first, second = printed[a], printed[b]
        notes = first.notes + tuple((o + first.length, *rest) for o, *rest in second.notes)
        return Bar("m", tuple(sorted(notes)), first.length + second.length, Fraction(4))

    unfolded = [printed[0], printed[1], printed[2], merged(3, 0), printed[1], printed[2], merged(3, 4), printed[5]]
    path, distances = align(printed, unfolded)
    assert path == [(0, 0), (1, 1), (2, 2), (3, 0), (1, 1), (2, 2), (3, 4), (5, 5)]
    assert max(distances) == 0


# ---------------------------------------------------------------- with the archive's fixture members
@pytest.fixture(scope="module")
def source():
    return convert.RemoteSource()


@pytest.fixture(scope="module")
def fixture_out(source, tmp_path_factory):
    out = tmp_path_factory.mktemp("bpsd-csv")
    convert.convert(FIXTURES, out, source=source, run_tilia=False)
    return out


def test_measure_grid(fixture_out, source):
    for item in FIXTURES:
        beats = read_csv(fixture_out / "csv" / item / "measures.csv")
        src = convert.annotation(source, "measure", item)
        assert len(beats) == len(src) == 202
        assert [b["time"] for b in beats] == [r["time"] for r in src]
        numbers = [int(b["measure"]) for b in beats]
        assert numbers[0] == 0 and numbers[1] == 1  # the pickup bar, then bar 1
        assert numbers[48] == 48 and numbers[49] == 1  # the repeated exposition shows its numbers again
        assert numbers[-1] == numbers[-2] + 1  # the end shows the number after the last bar
        assert numbers[-2] == 152 and max(numbers) == 153  # 200 unfolded bars, 152 printed
        assert float(src[0]["measure"]) == 0.75 and float(src[-1]["measure"]) == 200.25  # pickup, last partial bar


def test_structure_levels(fixture_out, source):
    for item in FIXTURES:
        out = read_csv(fixture_out / "csv" / item / "structure.csv")
        assert sorted({r["level"] for r in out}) == ["1", "2"]
        coarse = [r for r in out if r["level"] == "2"]
        fine = [r for r in out if r["level"] == "1"]
        assert [r["label"] for r in coarse] == ["Exposition", "Exposition", "Development", "Recapitulation"]
        assert {"FirstGroup", "Transition", "SecondGroup", "CadentialGroup"} <= {r["label"] for r in fine}
        assert not any(":" in r["label"] for r in out)


def test_keys_come_before_chords_and_every_chord_is_as_reported(fixture_out, source):
    from format_converters import _harte
    from format_converters.harmony import translate_chord, translate_key

    for item in FIXTURES:
        harmony = read_csv(fixture_out / "csv" / item / "harmony.csv")
        unparsed = read_csv(fixture_out / "csv" / item / "unparsed.csv")
        keys = convert.annotation(source, "localkey", item)
        chords = [c for c in convert.annotation(source, "chord", item) if c["shorthand"] not in ("N", "X", "")]
        assert [r["symbol"] for r in harmony if r["harmony_or_key"] == "key"] == \
            [translate_key(k["localkey"], "harte") for k in keys]
        times = [float(r["time"]) for r in harmony]
        assert times == sorted(times)
        for i, r in enumerate(harmony):  # a key never follows a chord that starts at its own time
            if r["harmony_or_key"] == "harmony":
                assert not any(h["harmony_or_key"] == "key" and h["time"] == r["time"] for h in harmony[i + 1:])
        expected, expected_unparsed = [], []
        for c in chords:
            key = translate_key(c["localkey"], "bps-fh")
            res = translate_chord(c["roman"], "bps-fh", key, _harte.pitch_classes(c["extended"]))
            if res.outcome == "none":
                expected_unparsed.append((c["start"], c["roman"], res.comments))
            else:
                expected.append((c["start"], res.symbol, res.display_mode, res.custom_text, res.comments))
        placed = [(r["time"], r["symbol"], r["display_mode"], r["custom_text"], r["comments"])
                  for r in harmony if r["harmony_or_key"] == "harmony"]
        assert placed == expected
        assert [(r["time"], r["label"], r["comments"]) for r in unparsed] == expected_unparsed
        assert all(r["display_mode"] in ("letter", "roman", "custom") for r in harmony)
        assert all(r["custom_text"] for r in harmony if r["display_mode"] == "custom")


def test_no_tilia_cli_writes_csvs_and_scripts(source, tmp_path):
    subprocess.run([sys.executable, str(CONVERT), "--out", str(tmp_path), "--only", FIXTURES[1], "--no-tilia"],
                   check=True, cwd=CONVERT.parents[1])
    assert (tmp_path / "csv" / FIXTURES[1] / "harmony.csv").exists()
    assert (tmp_path / "scripts" / f"{FIXTURES[1]}.txt").exists()
    assert not list((tmp_path / "tla").glob("*.tla"))


# ---------------------------------------------------------------- through TiLiA
@pytest.fixture(scope="module")
def converted(tilia, tmp_path_factory):
    out = tmp_path_factory.mktemp("bpsd-tla")
    subprocess.run([sys.executable, str(CONVERT), "--out", str(out), "--only", *FIXTURES,
                    "--package", str(out / "package")], check=True, cwd=CONVERT.parents[1])
    return out


def timelines(path):
    data = json.loads(Path(path).read_text())
    return data, {t["name"]: t for t in data["timelines"].values() if t.get("name")}


def test_components_equal_source_rows(converted):
    summary = json.loads((converted / "summary.json").read_text())
    assert set(summary) == set(FIXTURES)
    for item, layers in summary.items():
        assert set(layers) == {"Measures", "Structure", "Harmony/keys", "Harmony/chords"}
        for layer, counts in layers.items():
            assert counts["components"] == counts["source_rows"], (item, layer)
    assert summary[FIXTURES[0]]["Measures"]["source_rows"] == 202


def test_tla_timelines_and_metadata(converted):
    for item in FIXTURES:
        data, tls = timelines(converted / "tla" / f"{item}.tla")
        assert {n: t["kind"] for n, t in tls.items()} == {
            "Measures": "Beat", "Structure": "Hierarchy",
            "Harmony": "Harmony", "Chords (unparsed)": "Marker"}
        meta = data["media_metadata"]
        assert meta["title"] == "Piano Sonata Op. 2 No. 1, i"
        assert meta["composer"] == "Ludwig van Beethoven"
        assert meta["performer"] in ("Alfred Brendel", "Artur Schnabel")
        assert meta["licence"] == "CC BY 3.0"
        assert "10.5281/zenodo.12783403" in meta["corpus"] and "v2" in meta["corpus"]
        assert "Zeitler" in meta["notes"] and "10.5334/tismir.196" in meta["notes"]
        assert meta["media length"] == float(convert.annotation(convert.RemoteSource(), "measure", item)[-1]["time"])
        nums = tls["Measures"]["measure_numbers"]
        assert nums[0] == 0 and nums[48] == 48 and nums[49] == 1
        assert not data["media_path"]


def test_package(converted):
    zips = list((converted / "package").glob("*.zip"))
    assert [z.name for z in zips] == ["bpsd-v2-tilia.zip"]
    with zipfile.ZipFile(zips[0]) as z:
        names = z.namelist()
        assert "bpsd-v2-tilia/LICENSE" in names and "bpsd-v2-tilia/NOTICE.md" in names
        assert "creativecommons.org/licenses/by/3.0" in z.read("bpsd-v2-tilia/LICENSE").decode()
        tlas = [n for n in names if n.endswith(".tla")]
        assert len(tlas) == 2
        for n in tlas:
            data = json.loads(z.read(n))
            assert data["file_path"] == "" and data["media_path"] == ""


def test_measure_rows_last_bar_starting_after_the_end_is_kept_before_it():
    # the shape of WK64's Op. 26 and Op. 31 No. 2: the end row lies before the last bar's start
    source = rows("time;measure\n1.0;1.000\n2.0;2.000\n3.0;3.000\n2.5;3.500")
    out = convert.measure_rows(source, (1, 2, 3), pickup=False)
    assert [r["time"] for r in out] == ["1.0", "2.0", "2.499", "2.5"]
    assert [r["measure"] for r in out] == [1, 2, 3, 4]


# ---------------------------------------------------------------- the pickup comes from BPSD, not from bar lengths
def _musicxml(path, bars):
    """bars: (number, quarter notes of music); one C of that length per bar, a different octave per bar."""
    body = "".join(
        f'<measure number="{n}">' + ('<attributes><divisions>1</divisions><time><beats>4</beats>'
                                     '<beat-type>4</beat-type></time></attributes>' if i == 0 else "")
        + f'<note><pitch><step>C</step><octave>{i + 1}</octave></pitch><duration>{q}</duration></note></measure>'
        for i, (n, q) in enumerate(bars))
    path.write_text(f'<score-partwise><part-list/><part id="P1">{body}</part></score-partwise>')
    return path


def test_short_first_bar_without_annotated_pickup_is_not_a_pickup(tmp_path):
    from bpsd.bars import printed_numbers
    bars = [(1, 2), (2, 4), (3, 4), (4, 4)]  # a first bar of 2 quarter notes in 4/4, like a slow introduction
    printed = _musicxml(tmp_path / "printed.xml", bars)
    unfolded = _musicxml(tmp_path / "unfolded.xml", bars)
    numbers, distances = printed_numbers(printed, unfolded, pickup=False)
    assert numbers == [1, 2, 3, 4] and max(distances) == 0
    numbers, _ = printed_numbers(printed, unfolded, pickup=True)
    assert numbers == [0, 1, 2, 3]  # the same score, when BPSD does annotate a pickup


class _Measures:
    def __init__(self, first):
        self.first = first

    def path(self, member):
        performer = member.rsplit("_", 1)[1].split(".")[0]
        text = f"time;measure\n0.0;{self.first[performer]}\n1.0;1.000\n"
        p = Path(self.tmp) / f"{performer}.csv"
        p.write_text(text)
        return p


def test_performances_must_agree_on_a_pickup(tmp_path):
    source = _Measures({p: "000.750" for p in convert.PERFORMERS})
    source.tmp = tmp_path
    assert convert.has_pickup(source, "Op002No1-01") is True
    source = _Measures({p: "001.000" for p in convert.PERFORMERS})
    source.tmp = tmp_path
    assert convert.has_pickup(source, "Op078-01") is False
    source = _Measures({**{p: "001.000" for p in convert.PERFORMERS}, "WK64": "000.750"})
    source.tmp = tmp_path
    with pytest.raises(ValueError, match="disagree on a pickup"):
        convert.has_pickup(source, "Op078-01")


def test_op078_has_no_pickup_bar_and_unshifted_numbers(source, tmp_path):
    # a 7/4 first bar (the slow introduction) is not a pickup: BPSD's bars start at 001.000
    convert.convert(["Op078-01_AB96"], tmp_path, source=source, run_tilia=False)
    beats = read_csv(tmp_path / "csv" / "Op078-01_AB96" / "measures.csv")
    src = convert.annotation(source, "measure", "Op078-01_AB96")
    assert len(beats) == len(src) and float(src[0]["measure"]) == 1.0
    numbers = [int(b["measure"]) for b in beats]
    assert numbers[0] == 1 and 0 not in numbers
    # the Adagio's last bar (2/4) is split in the MusicXML into bars 4 and 5 by the double bar line before the
    # Allegro; BPSD's unfolded score has it as one bar, and the Allegro starts at 5, as in the editions
    assert numbers[:6] == [1, 2, 3, 4, 5, 6]
    assert numbers[-2] == 108  # the printed score has 109 bars, one of them the other half of bar 4
    assert numbers[-1] == numbers[-2] + 1


# ---------------------------------------------------------------- the repeat jumps of all 32 movements
# Backward jumps that do not land on the bar the signs send them to, as (movement, bar it leaves, bar it lands
# on) in MusicXML numbers, with the reason.
EXCEPTIONS = {
    ("Op027No1-01", 47, 40): "bar 39 is a half bar that holds the forward sign and counts with the bar before "
                             "it (the split-bar rule), so the unfolded bar after bar 47 starts in bar 40",
}


def _archive_source():
    """The downloaded archive when it is in the cache, else the members one by one."""
    cached = sorted(Path(convert.default_cache_dir()).glob("*Beethoven_Piano_Sonata_Dataset_v2.zip"))
    return convert.ZipSource(cached[0]) if cached else convert.RemoteSource()


def _jumps(source, piece):
    """The printed bars and every jump of the alignment, as (bar it leaves, bar it lands on), as indices into the
    printed bars. A unit that merges the end of a section with the pickup after the repeat (bars (a, b) with
    b != a + 1) has its jump inside it."""
    from bpsd.bars import read_bars
    printed = read_bars(source.path(f"0_RawData/score_xml_repetitions/Beethoven_{piece}.xml"))
    flat = read_bars(source.path(f"0_RawData/score_xml_unfolded/Beethoven_{piece}.xml"))
    path, _ = align(printed, flat)
    jumps = [(a, b) for a, b in path if b not in (a, a + 1)]
    jumps += [(a, b) for (_, a), (b, _) in zip(path, path[1:]) if b != a + 1]
    return printed, jumps


@pytest.mark.full
def test_every_backward_jump_leaves_a_closing_sign_and_lands_on_its_section():
    from bpsd.bars import repeat_target
    source = _archive_source()
    wrong, seen, used = [], 0, set()
    for piece in sorted({i.rpartition("_")[0] for i in convert.ITEMS}):
        printed, jumps = _jumps(source, piece)
        for a, b in jumps:
            if b > a:
                continue  # forward: a first ending skipped, not a repeat
            seen += 1
            key = (piece, int(printed[a].number), int(printed[b].number))
            if key in EXCEPTIONS:
                used.add(key)
            elif not (printed[a].repeat_end and repeat_target(printed, a) == b):
                wrong.append(key)
    assert seen >= 29
    assert not wrong, f"backward jumps off the repeat signs: {wrong}"
    assert used == set(EXCEPTIONS), "an exception that no jump needs any more"


@pytest.mark.full
@pytest.mark.parametrize("piece, jumps", [
    ("Op031No1-01", [(114, 4)]),  # the same notes before both signs: not 112 -> 2
    ("Op053-01", [(87, 3)]),  # not 86 -> 2
    ("Op079-01", [(50, 2), (174, 53)]),  # not 172 -> 51
    ("Op027No1-01", [(4, 1), (8, 5), (13, 10), (47, 40)]),
])
def test_jumps_are_on_the_signs_not_early(piece, jumps):
    printed, found = _jumps(_archive_source(), piece)
    assert [(int(printed[a].number), int(printed[b].number)) for a, b in found if b <= a] == jumps


@pytest.mark.full
def test_op010no2_numbers_never_go_back_but_at_the_exposition_repeat():
    source = _archive_source()
    printed, jumps = _jumps(source, "Op010No2-01")
    # the printed score goes on past the first endings, which the unfolded score lacks: forward skips only
    assert [(int(printed[a].number), int(printed[b].number)) for a, b in jumps if b > a + 1] == [(67, 69), (205, 207)]
    numbers, pickup = convert.bar_numbers(source, "Op010No2-01")
    assert pickup
    steps = [(a, b) for a, b in zip(numbers, numbers[1:]) if b < a]
    assert steps == [(66, 1)]  # only the exposition repeat goes back
    # printed bars 119/120 and 139/140 are each two halves of one 2/4 bar, cut by a fermata and a double bar line.
    # The unfolded score has one bar for each; it shows the first half's number and the bars after it count
    # one less: no number is skipped around them.
    assert numbers[178:190] == tuple(range(113, 125))
    assert numbers[198:206] == tuple(range(133, 141))
    assert numbers[-2:] == (202, 204)  # the first ending of the last repeat is not in the unfolded score
