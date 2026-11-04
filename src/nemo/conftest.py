"""What the package's own tests may ask for by name.

`seal` is defined in `nemo.test_purity` beside the test that proves it is not vacuous, and is
registered here so the module that uses it — `nemo.test_evidence` — takes it as a
fixture argument rather than as an import. Importing a fixture is what ruff reads as a
redefinition at every test that names it (F811); a conftest is where pytest looks anyway.
"""

from nemo.test_purity import seal  # noqa: F401  — registered for the whole package
