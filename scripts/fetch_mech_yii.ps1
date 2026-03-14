param(
    [string[]]$Args
)

$env:PYTHONPATH = "src"
python -m getmeajob.cli adzuna @Args