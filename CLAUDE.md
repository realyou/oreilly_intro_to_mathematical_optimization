# Intro to Mathematical Optimization (O'Reilly course materials)

Teaching materials, not a software product. Keep examples short and readable; the audience is
learners following the slides. Don't "productionise" the scripts.

## Layout

- `outline.md` is the course agenda; `code/section_N/` matches section N of the outline.
- `code/homework_answers/` holds the post-class homework solutions.
- `code/**/*.txt` are pointers to Java/Kotlin demo repos on GitHub, not source code.
- `slides/` and the root `.pptx`/`.pdf` are the slide deck. `demos/` are prebuilt Java 8 JARs.
- `videos/` are recordings. Never edit binaries in `slides/`, `demos/`, or `videos/`.

## Running the code

```bash
pip install -r requirements.txt
python3 code/section_4/lp1.py
```

- Python 3 scripts are standalone; run each one directly. There is no test suite.
- PuLP must be 3.x (`requirements.txt` pins it). PuLP 4 changed the API and breaks every solver script.
- Some scripts download CSVs from `tinyurl.com` and `bit.ly` at runtime. In a cloud session those
  hosts must be allowed in the environment's network settings, or the data must be vendored locally.
- Hill-climbing and simulated-annealing scripts are randomised; outputs differ between runs.

## Known breakage (survey on 2026-10-16, Python 3.13)

- `DataFrame.append` was removed in pandas 2: `linear_regression_hc.py`, `quadratic_regression_hc.py`,
  `quantile_regression_hc.py`, `quadratic_quantile_regression.py`. Replace with `pd.concat`.
- `section_2/logarithm_hc.py` calls `calculate_log`, which doesn't exist; the function is named `log`.
- `homework_answers/hw_2.py` writes `sudokuout.txt` to the working directory.

## Rules for changes

- Fix one script per commit and run it before and after; paste the last lines of output in the PR.
- Don't change the numeric examples that appear on the slides without flagging it in the PR.
- Prefer the smallest change that makes a script run on current library versions.
