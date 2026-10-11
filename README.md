# Local Job Agent

A Python proof of concept for job discovery, Pakistan eligibility checks, transparent match scoring, clarification questions, resume drafts, and optional ATS form filling. Ambiguous geography and unknown applicant counts stay visible.

## Run

Create a virtual environment and run `python -m pip install -e .`. Copy `config/profile.example.yaml` to `config/profile.yaml` and `config/search.example.yaml` to `config/search.yaml`; enter your own verified facts. Run `python -m job_agent doctor`. Network discovery is best effort and depends on the public guest jobs surface.

Run `python -m unittest discover -s tests -v` for offline checks. The GIF runs the real matcher and eligibility classifier on fictional jobs and a fictional profile. No resume or application history is included.

External ATS autofill is a prototype; submission requires an explicit `--submit` instruction. Unknown fields block automatic submission. LinkedIn Easy Apply stays manual.

## Demo

![Project motion demo](docs/demo.gif)

The motion demo combines actual interface captures or actual Python results with an illustrated walkthrough. All inputs shown are fictional.
