import boto3
from behave import *
import os
import yaml

from botocore.exceptions import ClientError
from importlib.machinery import SourceFileLoader
from sceptre.plan.plan import SceptrePlan
from sceptre.context import SceptreContext
from sceptre.cli.helpers import CfnYamlLoader


def set_template_path(context, stack_name, template_name):
    sceptre_context = SceptreContext(
        command_path=stack_name + ".yaml",
        project_path=context.sceptre_dir
    )

    config_path = sceptre_context.full_config_path()

    template_path = os.path.join(
        sceptre_context.project_path,
        sceptre_context.templates_path,
        template_name
    )
    with open(os.path.join(config_path, stack_name + '.yaml')) as config_file:
        stack_config = yaml.safe_load(config_file)

    if "template_path" in stack_config:
        stack_config["template_path"] = template_path
    if "template" in stack_config:
        template_handler_type = stack_config["template"]["type"]
        if template_handler_type.lower() == 's3':
            segments = stack_config["template"]["path"].split('/')
            bucket = context.TEST_ARTIFACT_BUCKET_NAME
            key = "/".join(segments[1:])
            stack_config["template"]["path"] = f'{bucket}/{key}'
        else:
            stack_config["template"]["path"] = template_path

    with open(os.path.join(config_path, stack_name + '.yaml'), 'w') as config_file:
        yaml.safe_dump(stack_config, config_file, default_flow_style=False)


@given('the template for stack "{stack_name}" is "{template_name}"')
def step_impl(context, stack_name, template_name):
    set_template_path(context, stack_name, template_name)


@when('the user validates the template for stack "{stack_name}"')
def step_impl(context, stack_name):
    sceptre_context = SceptreContext(
        command_path=stack_name + '.yaml',
        project_path=context.sceptre_dir
    )

    sceptre_plan = SceptrePlan(sceptre_context)
    try:
        response = sceptre_plan.validate()
        context.response = response
    except ClientError as e:
        context.error = e


@when('the user validates the template for stack "{stack_name}" with ignore dependencies')
def step_impl(context, stack_name):
    sceptre_context = SceptreContext(
        command_path=stack_name + '.yaml',
        project_path=context.sceptre_dir,
        ignore_dependencies=True
    )

    sceptre_plan = SceptrePlan(sceptre_context)
    try:
        response = sceptre_plan.validate()
        context.response = response
    except ClientError as e:
        context.error = e


@when('the user generates the template for stack "{stack_name}"')
def step_impl(context, stack_name):
    sceptre_context = SceptreContext(
        command_path=stack_name + '.yaml',
        project_path=context.sceptre_dir
    )

    config_path = sceptre_context.full_config_path()
    template_path = sceptre_context.full_templates_path()
    with open(os.path.join(config_path, stack_name + '.yaml')) as config_file:
        stack_config = yaml.safe_load(config_file)

    if "template" in stack_config and stack_config["template"]["type"].lower() == "s3":
        segments = stack_config["template"]["path"].split('/')
        bucket = segments[0]
        key = "/".join(segments[1:])
        source_file = f'{template_path}/{segments[-1]}'
        boto3.client('s3').upload_file(source_file, bucket, key)
    else:
        config_path = sceptre_context.full_config_path()
        with open(os.path.join(config_path, stack_name + '.yaml')) as config_file:
            stack_config = yaml.safe_load(config_file)

    sceptre_plan = SceptrePlan(sceptre_context)
    try:
        context.output = sceptre_plan.generate()
    except Exception as e:
        context.error = e


@when('the user generates the template for stack "{stack_name}" with ignore dependencies')
def step_impl(context, stack_name):
    sceptre_context = SceptreContext(
        command_path=stack_name + '.yaml',
        project_path=context.sceptre_dir,
        ignore_dependencies=True
    )
    sceptre_plan = SceptrePlan(sceptre_context)
    try:
        context.output = sceptre_plan.generate()
    except Exception as e:
        context.error = e


@then('the output is the same as the contents of "{filename}" template')
def step_impl(context, filename):

    filepath = os.path.join(
        context.sceptre_dir, "templates", filename
    )
    with open(filepath) as template:
        body = template.read()
    for template in context.output.values():
        assert yaml.load(body, Loader=CfnYamlLoader) == yaml.load(template, CfnYamlLoader)


@then('the output is the same as the string returned by "{filename}"')
def step_impl(context, filename):
    filepath = os.path.join(
        context.sceptre_dir, "templates", filename
    )

    module = SourceFileLoader("template", filepath).load_module()
    body = module.sceptre_handler({})
    for template in context.output.values():
        assert body == template
