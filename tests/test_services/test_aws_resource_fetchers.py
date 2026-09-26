from unittest.mock import Mock

from botocore.exceptions import ClientError
import pytest

from app.parsers.normalizer import normalize_collection
from app.services.aws_resource_fetchers import (
    fetch_elastic_beanstalk_environments,
    fetch_iam_roles,
    fetch_lambda_functions,
)


def test_fetch_iam_roles_includes_tags():
    client = Mock()
    client.get_paginator.return_value.paginate.return_value = [
        {"Roles": [{"RoleName": "deploy", "Arn": "arn:aws:iam::123:role/deploy"}]}
    ]
    client.list_role_tags.return_value = {"Tags": [{"Key": "team", "Value": "platform"}]}

    result = fetch_iam_roles(client)

    client.list_role_tags.assert_called_once_with(RoleName="deploy")
    assert result[0]["Tags"] == [{"Key": "team", "Value": "platform"}]


def test_fetch_iam_roles_defaults_tags_on_access_denied():
    client = Mock()
    client.exceptions.ClientError = ClientError
    client.get_paginator.return_value.paginate.return_value = [
        {"Roles": [{"RoleName": "restricted"}]}
    ]
    client.list_role_tags.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "denied"}},
        "ListRoleTags",
    )

    result = fetch_iam_roles(client)

    assert result[0]["Tags"] == []


def test_fetch_iam_roles_reraises_unexpected_tag_error():
    client = Mock()
    client.exceptions.ClientError = ClientError
    client.get_paginator.return_value.paginate.return_value = [
        {"Roles": [{"RoleName": "broken"}]}
    ]
    client.list_role_tags.side_effect = ClientError(
        {"Error": {"Code": "Throttling", "Message": "slow down"}},
        "ListRoleTags",
    )

    with pytest.raises(ClientError, match="Throttling"):
        fetch_iam_roles(client)


def test_fetch_lambda_functions_includes_tags():
    client = Mock()
    client.get_paginator.return_value.paginate.return_value = [
        {"Functions": [{"FunctionName": "worker", "FunctionArn": "arn:lambda:worker"}]}
    ]
    client.list_tags.return_value = {"Tags": {"team": "platform"}}

    result = fetch_lambda_functions(client)

    assert result[0]["Tags"] == {"team": "platform"}


def test_fetch_elastic_beanstalk_environments():
    client = Mock()
    client.get_paginator.return_value.paginate.return_value = [
        {"Environments": [{"EnvironmentId": "e-123", "EnvironmentName": "prod"}]}
    ]

    assert fetch_elastic_beanstalk_environments(client)[0]["EnvironmentId"] == "e-123"


def test_normalize_new_aws_resource_types():
    resources = normalize_collection(
        {
            "lambda_functions": [
                {
                    "FunctionName": "worker",
                    "FunctionArn": "arn:aws:lambda:us-east-1:123:function:worker",
                    "Tags": {"team": "platform"},
                }
            ],
            "elastic_beanstalk_environments": [
                {
                    "EnvironmentId": "e-123",
                    "EnvironmentName": "prod",
                    "EnvironmentArn": "arn:aws:elasticbeanstalk:us-east-1:123:environment/app/prod",
                }
            ],
        }
    )

    assert [(item.resource_id, item.resource_type, item.resource_name, item.arn) for item in resources] == [
        (
            "worker",
            "lambda_function",
            "worker",
            "arn:aws:lambda:us-east-1:123:function:worker",
        ),
        (
            "e-123",
            "elastic_beanstalk_environment",
            "prod",
            "arn:aws:elasticbeanstalk:us-east-1:123:environment/app/prod",
        ),
    ]


def test_normalize_lambda_requires_identity_fields():
    with pytest.raises(ValueError, match="FunctionArn"):
        normalize_collection({"lambda_functions": [{"FunctionName": "worker"}]})