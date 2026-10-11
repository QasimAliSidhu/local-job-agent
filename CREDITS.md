# Credits and source references

The application workflow is local project code. The repositories below supply integrated tools, libraries or fonts; they are not claimed as original implementations by this project. This audit did not identify an upstream application fork for this public project.

- [Playwright for Python](https://github.com/microsoft/playwright-python) — optional ATS browser autofill.
- [pypdf](https://github.com/py-pdf/pypdf) — PDF resume text extraction.
- [Jinja](https://github.com/pallets/jinja) — resume templates.
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) — MCP server interface.

## Recording

The demo records isolated local workflows using fictional data. Playwright ([Python repository](https://github.com/microsoft/playwright-python)) drives the cursor and interactions; FFmpeg encodes the recording. Camera crops, zooms and captions are added after capture.

The demo terminal plays fresh stdout from `python examples/offline_demo.py`; it is a presentation of the actual matcher and eligibility results, not a new application GUI.
