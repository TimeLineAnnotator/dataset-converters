# Dezrann's structure and texture of Mozart's piano sonatas, as TiLiA CSVs

For each of the nine movements of Mozart's sonatas K. 279, 280 and 283 (K279-1 to K283-3), two CSV files
with the sonata-form structure (`<piece>-structure.csv`, two levels: sections over subjects and transitions)
and the texture (`<piece>-texture.csv`, one level) annotated in Dezrann's *Mozart piano sonatas* dataset,
v1.0 (2024-12-18), https://doi.org/10.57745/OHRWPC.

## Licence and attribution

The annotations are licensed under the Open Data Commons Open Database License 1.0 (ODbL), see `LICENSE`.
These CSVs are a derived database and carry the same licence. As the dataset asks, please attribute:

> Couturier, L., Bigo, L., Hentschel, J., Levé, F., Neuwirth, M. and Rohrmeier, M. (2024). Mozart piano
> sonatas (v1.0). Recherche Data Gouv. https://doi.org/10.57745/OHRWPC

## What the CSVs are

One row per label, by bar, in the columns of TiLiA's hierarchy import by measure: `start`,
`start_fraction`, `end`, `end_fraction`, `level`, `label`, `comments`. The bar numbers are those of
Dezrann's measure maps, which agree with the printed bar numbers of DCML's annotated Mozart sonatas.
Where a bar number occurs twice (first and second endings), a by-measure import places a label in both:
if that matters, import by time instead, or from the files built by `dezrann-mozart/convert.ipynb`.

## What was left out

Only the labels of type `Structure` and `Texture` are here. Left out:

- `Harmony`, `Cadence`, `Local Key` and `Phrase` labels: they are the DCML's own annotations, which
  Dezrann carries over and the DCML converter already provides;
- the `Positive Feedback` labels (a "doubt" with the annotators' discussion);
- the `Comment` labels (two, both in K283-2).

## Merged files

The notebook also builds, locally, TiLiA files with these layers added to the converted DCML files. They
are never packaged or shipped: they would hold the DCML's CC BY-NC-SA 4.0 timelines (share-alike,
non-commercial) next to ODbL ones (share-alike under another licence), and both terms cannot be met in one
file. Build them yourself with the notebook.
