# dataset-converters

Scripts that turn published music-analysis datasets into [TiLiA](https://github.com/TimeLineAnnotator/desktop) files. Each dataset has a folder of its own.

| Folder | Dataset | Formerly |
| --- | --- | --- |
| `bpsd/` | Beethoven Piano Sonata Dataset | `TimeLineAnnotator/bpsd-to-tilia` |
| `dcml-mozart/` | DCML annotations of Mozart's piano sonatas | `TimeLineAnnotator/dcml-to-tilia` |

The datasets themselves are not stored here: the converters download them, and the TiLiA files they produce are build outputs.

The code is under the MIT licence. The datasets keep their own licences.
