"""Eval command — run eval suites against agent configs."""

import asyncio
import json
import sys

import click


@click.command("eval")
@click.argument("suite_path", type=click.Path(exists=True))
@click.option("--json", "json_output", is_flag=True, help="Output results as JSON.")
@click.pass_context
def eval_cmd(ctx, suite_path, json_output):
    """Run an eval suite against an agent config."""
    from woodwork.eval.loader import load_suite
    from woodwork.eval.runner import EvalRunner

    suite = load_suite(suite_path)
    runner = EvalRunner()
    report = asyncio.run(runner.run(suite))

    if json_output:
        click.echo(json.dumps(report.to_dict(), indent=2))
    else:
        report.print_report()

    sys.exit(0 if report.failed == 0 else 1)
