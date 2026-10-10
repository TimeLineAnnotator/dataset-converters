import json
import wave
import zipfile

import pytest

from swd import convert
from swd.tests.conftest import ITEMS, components, read_tla

SONG1, SONG2 = ITEMS


def source_rows(data, name):
    return data[name]


# ---------------------------------------------------------------- the measure grid
def test_measures_follow_the_audio_file_with_printed_numbers(data, written):
    rows = written[SONG1]["measures"]
    audio = data[SONG1]["measure"]
    assert len(rows) == len(audio) == 138
    assert [r["time"] for r in rows] == [r["start"] for r in audio]
    assert {r["is_first_in_measure"] for r in rows} == {"true"}
    numbers = [int(r["measure"]) for r in rows]
    # song 1 unfolds its repeat: bar 39 of the performance is printed bar 7, row 50 is printed bar 18
    assert numbers[:3] == [1, 2, 3]
    assert numbers[37:40] == [38, 7, 8]
    assert numbers[49] == 18
    assert numbers[-2:] == [105, 106]  # the last row is the end: the number after the last bar


def test_a_pickup_is_bar_zero(data, written):
    rows = written[SONG2]["measures"]
    assert data[SONG2]["measure"][0]["measure"] == "0.750"
    assert (rows[0]["time"], rows[0]["measure"]) == ("0.293877551", "0")
    assert [r["measure"] for r in rows[1:3]] == ["1", "2"]
    assert (len(rows), rows[-1]["measure"]) == (53, "52")


def test_printed_numbers_need_one_audio_row_more_than_score_bars():
    d = {"item": "x", "measure": [{}] * 3, "printed": [{"measure": "1"}] * 3}
    with pytest.raises(ValueError, match="x: 3 audio measure rows for 3 score bars"):
        convert.printed_numbers(d)


# ---------------------------------------------------------------- structure
def test_structure_has_one_level(data, written):
    rows = written[SONG2]["structure"]
    assert {r["level"] for r in rows} == {"1"}
    assert [r["label"] for r in rows] == [r["structure"] for r in data[SONG2]["structure"]]
    assert (rows[0]["start"], rows[0]["end"], rows[0]["label"]) == ("0.3", "8.64", "I1")


# ---------------------------------------------------------------- harmony
def test_annotator_1s_keys_are_the_harmony_timelines_keys(data, written):
    for item, key in ((SONG1, "c"), (SONG2, "g")):  # HU33 sings song 1 in C minor, song 2 in G minor
        rows = written[item]["harmony"]
        assert (rows[0]["harmony_or_key"], rows[0]["symbol"]) == ("key", key)
        assert rows[0]["time"] == rows[1]["time"]  # the key comes before the chord at the same time
        keys = [(r["time"], r["symbol"]) for r in rows if r["harmony_or_key"] == "key"]
        assert keys == [(r["time"], r["symbol"]) for r in written[item]["localkeys-ann1"]]
    assert [k for _, k in keys][:3] == ["g", "B-", "d"]


def test_chords_show_as_roman_numerals(written):
    for item in ITEMS:
        modes = {r["display_mode"] for r in written[item]["harmony"] if r["harmony_or_key"] == "harmony"}
        assert modes == {"roman", "custom"}


def test_harte_chords_are_written_as_format_converters_report_them(written):
    rows = written[SONG1]["harmony"]
    c = next(r for r in rows if r["symbol"] == "Cm/G")  # C:min/G
    assert (c["display_mode"], c["custom_text"], c["comments"]) == ("roman", "", "")
    # B:dim7/C: TiLiA stores only Fdim/C, so it shows the label as custom text and says why
    approx = next(r for r in rows if r["custom_text"] == "B:dim7/C")
    assert approx["symbol"] == "Fdim/C"
    assert approx["display_mode"] == "custom"
    assert "Fdim/C" in approx["comments"]


def test_every_display_mode_is_filled_and_custom_has_text(written):
    for item in ITEMS:
        for name in ("harmony", "localkeys-ann1", "localkeys-ann2", "localkeys-ann3"):
            for r in written[item][name]:
                assert r["display_mode"] in ("letter", "roman", "custom")
                assert r["display_mode"] != "custom" or r["custom_text"]


def test_no_chord_labels_are_not_placed_and_unparsed_ones_become_markers(data, written):
    d = data[SONG2]
    chords = [r for r in d["chord"] if convert.is_chord(r)]
    harmony = [r for r in written[SONG2]["harmony"] if r["harmony_or_key"] == "harmony"]
    unparsed = written[SONG2]["unparsed"]
    assert len(harmony) + len(unparsed) == len(chords)
    assert unparsed[0] == {"time": "1.56", "label": "D:(b9)",
                           "comments": "no symbol that TiLiA's parser reads as this chord"}
    assert "D:(b9)" not in [r["custom_text"] for r in harmony]


def test_n_and_x_rows_are_not_chords_and_do_not_move_the_key(data):
    d = dict(data[SONG2])
    pad = {"start": "0", "end": "0.3", "shorthand": "N", "extended": "N"}
    pads = [pad, dict(pad, shorthand="X", extended="X"), dict(pad, shorthand="")]
    d["chord"] = [*pads, *d["chord"]]
    d["score_chord"] = [*pads, *d["score_chord"]]
    harmony = convert.build_tables(d)["harmony"][1]
    assert sum(r[0] == "harmony" for r in harmony) == 66 and harmony[0][1] == "0.3"
    assert convert.source_rows(d)["Harmony/chords"] == 69


# ---------------------------------------------------------------- local keys
def test_local_keys_are_keys_only(data, written):
    for n in (1, 2, 3):
        rows = written[SONG2][f"localkeys-ann{n}"]
        assert [r["time"] for r in rows] == [r["start"] for r in data[SONG2]["localkey"][n]]
        assert {r["harmony_or_key"] for r in rows} == {"key"}
    assert [r["symbol"] for r in written[SONG2]["localkeys-ann1"][:3]] == ["g", "B-", "d"]  # A#:maj is written as B-flat major


# ---------------------------------------------------------------- the script
def test_script_has_metadata_then_media_then_timelines(data, tmp_path):
    d = data[SONG2]
    paths = convert.write_tables(convert.build_tables(d), tmp_path)
    script = convert.write_script(d, paths, tmp_path / "x.tla").splitlines()
    assert script[0] == 'metadata set "title" "Winterreise, D 911: 2. Die Wetterfahne"'
    assert 'metadata set "performer" "Hüsch (HU33)"' in script
    assert 'metadata set "licence" "CC BY 3.0"' in script
    assert script[5].startswith('metadata set "notes" "Schubert Winterreise Dataset')
    assert script[6] == "metadata set-media-length 95.9"
    adds = [l.split("--name ")[1].split(" ")[0] for l in script if l.startswith("timelines add")]
    assert adds == ['"Measures"', '"Structure"', '"Harmony"', '"Local', '"Local', '"Local', '"Chords']
    assert not any("by-measure" in l for l in script)
    assert script[-1] == f"save {tmp_path / 'x.tla'} --overwrite"
    def wav(name, seconds):
        path = tmp_path / name
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1), w.setsampwidth(1), w.setframerate(100)
            w.writeframes(bytes(int(seconds * 100)))
        return path

    # a recording that outlasts the annotations is left alone; one that ends before them gets their length,
    # since TiLiA refuses annotations past the media
    long = convert.write_script(d, paths, tmp_path / "x.tla", recording=wav("long.wav", 100))
    assert f"load-media {tmp_path / 'long.wav'}" in long and "set-media-length" not in long
    short = convert.write_script(d, paths, tmp_path / "x.tla", recording=wav("short.wav", 90))
    assert "load-media" in short and "metadata set-media-length 95.9" in short.splitlines()[7]


def test_metadata_values_have_no_double_quotes(data):
    for d in data.values():
        assert all('"' not in v for v in convert.metadata(d).values())


# ---------------------------------------------------------------- through TiLiA
def test_tla_counts_equal_source_rows(converted):
    out, summary = converted
    assert sorted(summary) == sorted(ITEMS)
    for item, layers in summary.items():
        assert list(layers) == convert.LAYERS
        for layer, counts in layers.items():
            assert counts["components"] == counts["source_rows"], (item, layer)
    assert summary[SONG1]["Measures"]["source_rows"] == 138
    assert summary[SONG2]["Harmony/chords"]["source_rows"] == 69


def test_tla_timelines_and_bar_numbers(converted):
    out, _ = converted
    for item in ITEMS:
        _, tl = read_tla(out / "tla" / f"{item}.tla")
        kinds = {n: t["kind"] for n, t in tl.items()}
        assert kinds == {"Measures": "Beat", "Structure": "Hierarchy", "Harmony": "Harmony",
                         "Local keys (ann1)": "Harmony", "Local keys (ann2)": "Harmony",
                         "Local keys (ann3)": "Harmony", "Chords (unparsed)": "Marker"}
    _, tl = read_tla(out / "tla" / f"{SONG1}.tla")
    numbers = tl["Measures"]["measure_numbers"]
    assert numbers[37:40] == [38, 7, 8] and numbers[49] == 18
    _, tl = read_tla(out / "tla" / f"{SONG2}.tla")
    assert tl["Measures"]["measure_numbers"][:2] == [0, 1]
    assert {c["level"] for c in components(tl["Structure"])} == {1}


def test_tla_chords_as_reported(converted):
    out, _ = converted
    _, tl = read_tla(out / "tla" / f"{SONG2}.tla")
    assert [c["kind"] for c in components(tl["Harmony"])].count("MODE") == 12
    assert [c["time"] for c in components(tl["Chords (unparsed)"])][:2] == [1.56, 3.16]
    keys = components(tl["Local keys (ann1)"])
    assert {c["kind"] for c in keys} == {"MODE"} and len(keys) == 12


def test_tla_chord_display(converted, tilia_keeps_harmony_display):
    if not tilia_keeps_harmony_display:
        pytest.skip("this TiLiA drops the harmony CSV's display_mode and custom_text (TimeLineAnnotator/desktop#631)")
    out, _ = converted
    _, tl = read_tla(out / "tla" / f"{SONG2}.tla")
    custom = [c for c in components(tl["Harmony"]) if c["kind"] == "HARMONY" and c["display_mode"] == "custom"]
    assert {c["custom_text"] for c in custom} == {"G:(3,5,b7,b9)/B", "G:(3,b5,b7,b9)/Db"}  # spelled from the score
    assert all(c["comments"] for c in custom)


def test_tla_metadata(converted):
    out, _ = converted
    data, _ = read_tla(out / "tla" / f"{SONG1}.tla")
    md = data["media_metadata"]
    assert md["title"] == "Winterreise, D 911: 1. Gute Nacht"
    assert md["composer"] == "Franz Schubert" and md["licence"] == "CC BY 3.0"
    assert "doi:10.5281/zenodo.10839767" in md["corpus"] and "Weiß" in md["notes"]
    assert md["media length"] == pytest.approx(convert.media_length(convert.read_item(convert.Source.open(), SONG1)))


# ---------------------------------------------------------------- the package
def test_package_has_no_paths_and_carries_licence_and_notice(converted, tmp_path):
    out, _ = converted
    path = convert.package(out, tmp_path)
    assert path.name == "swd-v2.1-tilia.zip"
    z = zipfile.ZipFile(path)
    names = z.namelist()
    assert "swd-v2.1-tilia/LICENSE" in names and "swd-v2.1-tilia/NOTICE.md" in names
    assert "creativecommons.org/licenses/by/3.0" in z.read("swd-v2.1-tilia/LICENSE").decode()
    notice = z.read("swd-v2.1-tilia/NOTICE.md").decode()
    for text in ("Public Domain Mark 1.0", "CC BY-NC-ND 3.0", "commercial recordings", "10.5281/zenodo.10839767"):
        assert text in notice
    tlas = [n for n in names if n.endswith(".tla")]
    assert len(tlas) == 2
    for n in tlas:
        d = json.loads(z.read(n))
        assert d["file_path"] == "" and d["media_path"] == ""
    assert convert.package(out, tmp_path).read_bytes() == path.read_bytes()
