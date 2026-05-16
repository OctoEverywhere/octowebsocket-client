# This is a small PowerShell script to upload new releases to PyPI from Windows.
# Run with:
#   powershell -ExecutionPolicy Bypass -File .\upload.sh
# or:
#   pwsh -File .\upload.sh

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-Python {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]] $Arguments
    )

    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 @Arguments
    }
    else {
        & python @Arguments
    }

    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

function Remove-BuildArtifacts {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue `
        .\build, `
        .\dist, `
        .\octowebsocket_client.egg-info
}

# Start from clean build artifacts so old distributions are not uploaded.
Remove-BuildArtifacts

# Install release dependencies into the active Python environment.
Invoke-Python -m pip install -U build twine

# Build the package.
Invoke-Python -m build

$distFiles = @(Get-ChildItem -Path .\dist -File | ForEach-Object { $_.FullName })
if ($distFiles.Count -eq 0) {
    throw "No distribution files were created in .\dist."
}

# Run Twine check to verify descriptions are valid.
Invoke-Python -m twine check @distFiles

# Upload to TestPyPI first to verify everything.
# The secure approach is to use an API token, then pass __token__ as the
# username and the token value as the password.
# https://packaging.python.org/en/latest/tutorials/packaging-projects/#uploading-the-distribution-archives
# Invoke-Python -m twine upload --repository testpypi @distFiles

# Now upload to production PyPI.
# The secure approach is to use an API token, then pass __token__ as the
# username and the token value as the password.
# https://packaging.python.org/en/latest/tutorials/packaging-projects/#uploading-the-distribution-archives
Invoke-Python -m twine upload @distFiles

# Clean up build artifacts after a successful upload.
Remove-BuildArtifacts
