"""Authentication stack for A360 Transcription Service Evaluator.

This stack creates AWS Cognito User Pool with groups and Amazon Verified
Permissions for fine-grained authorization following AWS best practices.
"""

import json

import aws_cdk as cdk
from aws_cdk import Duration
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_verifiedpermissions as avp
from constructs import Construct


class AuthStack(cdk.NestedStack):
    """Authentication and authorization infrastructure stack."""

    def __init__(
        self, scope: Construct, construct_id: str, app_name: str, stage: str, **kwargs
    ):
        super().__init__(scope, construct_id, **kwargs)

        self.app_name = app_name
        self.stage = stage

        # Create Cognito User Pool
        self.user_pool = self._create_user_pool()

        # Create User Pool Client
        self.user_pool_client = self._create_user_pool_client()

        # Create Identity Pool for Amplify compatibility
        self.identity_pool = self._create_identity_pool()

        # Create User Groups for RBAC
        self.user_groups = self._create_user_groups()

        # Create Verified Permissions Policy Store
        self.policy_store = self._create_verified_permissions_policy_store()

        # Create Lambda triggers for user lifecycle
        self._create_lambda_triggers()

    def _create_user_pool(self) -> cognito.UserPool:
        """Create Cognito User Pool with security best practices."""

        # Custom message Lambda for email customization
        custom_message_lambda = lambda_.Function(
            self,
            "CustomMessageLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_inline('''
import json

def handler(event, context):
    if event['triggerSource'] == 'CustomMessage_AdminCreateUser':
        event['response']['smsMessage'] = f"Welcome to A360 Transcription Evaluator! Your temporary password is {event['request']['codeParameter']}"
        event['response']['emailMessage'] = f"""Welcome to A360 Transcription Evaluator!

Your temporary password is: {event['request']['codeParameter']}

Please login and change your password immediately.

Best regards,
A360 Team"""
        event['response']['emailSubject'] = "Welcome to A360 Transcription Evaluator"
    
    return event
            '''),
            description="Custom message Lambda for Cognito",
            timeout=Duration.seconds(30),
        )

        user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name=f"{self.app_name}-{self.stage}-user-pool",
            # Self sign-up disabled for controlled access
            self_sign_up_enabled=False,
            # Sign-in configuration
            sign_in_aliases=cognito.SignInAliases(
                email=True, username=False, phone=False
            ),
            # Auto verification
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            # Standard attributes - cannot modify existing user pool attributes
            # Custom attributes for RBAC
            custom_attributes={
                "department": cognito.StringAttribute(mutable=True),
                "role_level": cognito.NumberAttribute(mutable=True, min=1, max=4),
            },
            # Password policy
            password_policy=cognito.PasswordPolicy(
                min_length=12,
                require_uppercase=True,
                require_lowercase=True,
                require_digits=True,
                require_symbols=True,
                temp_password_validity=Duration.days(3),
            ),
            # MFA configuration
            mfa=cognito.Mfa.OPTIONAL,
            mfa_second_factor=cognito.MfaSecondFactor(
                sms=False,  # Disable SMS for security
                otp=True,  # Enable TOTP apps
            ),
            # Account recovery
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            # Advanced security disabled for standard tier
            # Device tracking
            device_tracking=cognito.DeviceTracking(
                challenge_required_on_new_device=True,
                device_only_remembered_on_user_prompt=True,
            ),
            # Lambda triggers
            lambda_triggers=cognito.UserPoolTriggers(
                custom_message=custom_message_lambda
            ),
            # Deletion protection
            deletion_protection=True if self.stage == "prod" else False,
            # Email configuration
            email=cognito.UserPoolEmail.with_cognito(),
            # User verification
            user_verification=cognito.UserVerificationConfig(
                email_subject="Verify your A360 Transcription Evaluator account",
                email_body="Thank you for signing up! Your verification code is {####}",
                email_style=cognito.VerificationEmailStyle.CODE,
            ),
        )

        # Add tags
        cdk.Tags.of(user_pool).add("Environment", self.stage)
        cdk.Tags.of(user_pool).add("Application", self.app_name)

        return user_pool

    def _create_user_pool_client(self) -> cognito.UserPoolClient:
        """Create User Pool Client for SPA authentication with Amplify."""

        client = self.user_pool.add_client(
            "UserPoolClient",
            user_pool_client_name=f"{self.app_name}-{self.stage}-client",
            # Auth flows for SPA
            auth_flows=cognito.AuthFlow(
                user_password=True,
                admin_user_password=True,
                user_srp=True,
                custom=False,  # Disable custom auth for security
            ),
            # Token validity
            access_token_validity=Duration.hours(1),
            id_token_validity=Duration.hours(1),
            refresh_token_validity=Duration.days(30),
            # Security for SPA
            generate_secret=False,  # Required for public clients (SPA)
            prevent_user_existence_errors=True,
            enable_token_revocation=True,
            # Explicitly disable OAuth to remove existing configuration
            supported_identity_providers=[cognito.UserPoolClientIdentityProvider.COGNITO],
        )

        return client

    def _create_identity_pool(self) -> cognito.CfnIdentityPool:
        """Create Identity Pool for Amplify authentication."""

        identity_pool = cognito.CfnIdentityPool(
            self,
            "IdentityPool",
            identity_pool_name=f"{self.app_name}-{self.stage}-identity-pool",
            # Allow unauthenticated access for public API calls
            allow_unauthenticated_identities=True,
            # Configure User Pool as identity provider
            cognito_identity_providers=[
                cognito.CfnIdentityPool.CognitoIdentityProviderProperty(
                    client_id=self.user_pool_client.user_pool_client_id,
                    provider_name=self.user_pool.user_pool_provider_name,
                )
            ],
        )

        # Create IAM roles for authenticated and unauthenticated users
        self._create_identity_pool_roles(identity_pool)

        return identity_pool

    def _create_identity_pool_roles(
        self, identity_pool: cognito.CfnIdentityPool
    ) -> None:
        """Create IAM roles for Identity Pool users."""

        # Authenticated role (minimal permissions for API Gateway calls)
        authenticated_role = iam.Role(
            self,
            "IdentityPoolAuthenticatedRole",
            assumed_by=iam.FederatedPrincipal(
                "cognito-identity.amazonaws.com",
                {
                    "StringEquals": {
                        "cognito-identity.amazonaws.com:aud": identity_pool.ref
                    },
                    "ForAnyValue:StringLike": {
                        "cognito-identity.amazonaws.com:amr": "authenticated"
                    },
                },
            ),
            inline_policies={
                "APIGatewayInvoke": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["execute-api:Invoke"],
                            resources=["*"],
                        )
                    ]
                )
            },
        )

        # Unauthenticated role (very restricted)
        unauthenticated_role = iam.Role(
            self,
            "IdentityPoolUnauthenticatedRole",
            assumed_by=iam.FederatedPrincipal(
                "cognito-identity.amazonaws.com",
                {
                    "StringEquals": {
                        "cognito-identity.amazonaws.com:aud": identity_pool.ref
                    },
                    "ForAnyValue:StringLike": {
                        "cognito-identity.amazonaws.com:amr": "unauthenticated"
                    },
                },
            ),
            inline_policies={
                "DenyAll": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.DENY, actions=["*"], resources=["*"]
                        )
                    ]
                )
            },
        )

        # Attach roles to Identity Pool
        cognito.CfnIdentityPoolRoleAttachment(
            self,
            "IdentityPoolRoleAttachment",
            identity_pool_id=identity_pool.ref,
            roles={
                "authenticated": authenticated_role.role_arn,
                "unauthenticated": unauthenticated_role.role_arn,
            },
        )

    def _create_user_groups(self) -> dict:
        """Create user groups for role-based access control."""

        groups_config = [
            {
                "name": "admin",
                "description": "System administrators with full access to all resources and user management",
                "precedence": 1,
            },
            {
                "name": "reviewer",
                "description": "Senior evaluators who review and approve completed evaluations",
                "precedence": 2,
            },
            {
                "name": "evaluator",
                "description": "Quality assurance specialists who evaluate transcription quality",
                "precedence": 3,
            },
            {
                "name": "reader",
                "description": "Readers who create audio recordings for evaluation",
                "precedence": 4,
            },
        ]

        groups = {}
        for group_config in groups_config:
            group = cognito.CfnUserPoolGroup(
                self,
                f"{group_config['name'].title()}Group",
                user_pool_id=self.user_pool.user_pool_id,
                group_name=group_config["name"],
                description=group_config["description"],
                precedence=group_config["precedence"],
            )
            groups[group_config["name"]] = group

        return groups

    def _create_verified_permissions_policy_store(self) -> avp.CfnPolicyStore:
        """Create Amazon Verified Permissions policy store with Cedar policies."""

        # Cedar schema for our application
        cedar_schema = {
            "A360TranscriptionEvaluator": {
                "entityTypes": {
                    "User": {
                        "memberOfTypes": ["Group"],
                        "shape": {
                            "type": "Record",
                            "attributes": {
                                "email": {"type": "String"},
                                "department": {"type": "String"},
                                "role_level": {"type": "Long"},
                            },
                        },
                    },
                    "Group": {
                        "shape": {
                            "type": "Record",
                            "attributes": {"name": {"type": "String"}},
                        }
                    },
                    "Script": {
                        "shape": {
                            "type": "Record",
                            "attributes": {
                                "title": {"type": "String"},
                                "difficulty_level": {"type": "Long"},
                                "created_by": {"type": "String"},
                            },
                        }
                    },
                    "Assignment": {
                        "shape": {
                            "type": "Record",
                            "attributes": {
                                "script_id": {"type": "String"},
                                "assigned_to": {"type": "String"},
                                "assigned_by": {"type": "String"},
                                "assignment_type": {"type": "String"},
                                "status": {"type": "String"},
                            },
                        }
                    },
                    "Brand": {
                        "shape": {
                            "type": "Record",
                            "attributes": {
                                "name": {"type": "String"},
                                "vertical": {"type": "String"},
                                "created_by": {"type": "String"},
                            },
                        }
                    },
                    "Term": {
                        "shape": {
                            "type": "Record",
                            "attributes": {
                                "name": {"type": "String"},
                                "vertical": {"type": "String"},
                                "created_by": {"type": "String"},
                            },
                        }
                    },
                    "Job": {
                        "shape": {
                            "type": "Record",
                            "attributes": {
                                "job_id": {"type": "String"},
                                "user_id": {"type": "String"},
                                "status": {"type": "String"},
                                "created_by": {"type": "String"},
                            },
                        }
                    },
                },
                "actions": {
                    "ViewAssignment": {
                        "appliesTo": {
                            "resourceTypes": ["Assignment"],
                            "principalTypes": ["User"],
                        }
                    },
                    "UpdateAssignment": {
                        "appliesTo": {
                            "resourceTypes": ["Assignment"],
                            "principalTypes": ["User"],
                        }
                    },
                    "CreateAssignment": {
                        "appliesTo": {
                            "resourceTypes": ["Script"],
                            "principalTypes": ["User"],
                        }
                    },
                    "ManageUsers": {
                        "appliesTo": {
                            "resourceTypes": ["User"],
                            "principalTypes": ["User"],
                        }
                    },
                    "ViewUserStats": {
                        "appliesTo": {
                            "resourceTypes": ["User"],
                            "principalTypes": ["User"],
                        }
                    },
                    "GenerateGroundTruth": {
                        "appliesTo": {
                            "resourceTypes": ["Script"],
                            "principalTypes": ["User"],
                        }
                    },
                    "ManageBrands": {
                        "appliesTo": {
                            "resourceTypes": ["Brand"],
                            "principalTypes": ["User"],
                        }
                    },
                    "ViewBrands": {
                        "appliesTo": {
                            "resourceTypes": ["Brand"],
                            "principalTypes": ["User"],
                        }
                    },
                    "ManageTerms": {
                        "appliesTo": {
                            "resourceTypes": ["Term"],
                            "principalTypes": ["User"],
                        }
                    },
                    "ViewTerms": {
                        "appliesTo": {
                            "resourceTypes": ["Term"],
                            "principalTypes": ["User"],
                        }
                    },
                    "ManageJobs": {
                        "appliesTo": {
                            "resourceTypes": ["Job"],
                            "principalTypes": ["User"],
                        }
                    },
                    "ViewJobs": {
                        "appliesTo": {
                            "resourceTypes": ["Job"],
                            "principalTypes": ["User"],
                        }
                    },
                },
            }
        }

        policy_store = avp.CfnPolicyStore(
            self,
            "PolicyStore",
            validation_settings=avp.CfnPolicyStore.ValidationSettingsProperty(
                mode="STRICT"
            ),
            schema=avp.CfnPolicyStore.SchemaDefinitionProperty(
                cedar_json=json.dumps(cedar_schema)
            ),
            description=f"Policy store for {self.app_name} {self.stage} environment",
        )

        # Create Cedar policies for RBAC
        self._create_cedar_policies(policy_store)

        return policy_store

    def _create_cedar_policies(self, policy_store: avp.CfnPolicyStore):
        """Create Cedar policies for role-based access control."""

        policies = [
            # Admin policies - full access
            {
                "id": "AdminFullAccess",
                "statement": """
permit(
    principal in A360TranscriptionEvaluator::Group::"admin",
    action,
    resource
);
                """.strip(),
            },
            # Evaluator policies
            {
                "id": "EvaluatorViewOwnAssignments",
                "statement": """
permit(
    principal,
    action == A360TranscriptionEvaluator::Action::"ViewAssignment",
    resource
) when {
    principal in A360TranscriptionEvaluator::Group::"evaluator" &&
    resource.assigned_to == principal.email
};
                """.strip(),
            },
            {
                "id": "EvaluatorUpdateOwnAssignments",
                "statement": """
permit(
    principal,
    action == A360TranscriptionEvaluator::Action::"UpdateAssignment", 
    resource
) when {
    principal in A360TranscriptionEvaluator::Group::"evaluator" &&
    resource.assigned_to == principal.email &&
    resource.assignment_type == "evaluate"
};
                """.strip(),
            },
            # Reviewer policies
            {
                "id": "ReviewerViewAssignments",
                "statement": """
permit(
    principal in A360TranscriptionEvaluator::Group::"reviewer",
    action == A360TranscriptionEvaluator::Action::"ViewAssignment",
    resource
) when {
    resource.assignment_type == "review"
};
                """.strip(),
            },
            {
                "id": "ReviewerCreateAssignments",
                "statement": """
permit(
    principal in A360TranscriptionEvaluator::Group::"reviewer",
    action == A360TranscriptionEvaluator::Action::"CreateAssignment",
    resource
);
                """.strip(),
            },
            # Voice Actor policies - most restrictive
            {
                "id": "VoiceActorViewOwnAssignments",
                "statement": """
permit(
    principal,
    action == A360TranscriptionEvaluator::Action::"ViewAssignment",
    resource
) when {
    principal in A360TranscriptionEvaluator::Group::"reader" &&
    resource.assigned_to == principal.email &&
    resource.assignment_type == "record"
};
                """.strip(),
            },
            {
                "id": "VoiceActorUpdateOwnRecordingAssignments",
                "statement": """
permit(
    principal,
    action == A360TranscriptionEvaluator::Action::"UpdateAssignment",
    resource
) when {
    principal in A360TranscriptionEvaluator::Group::"reader" &&
    resource.assigned_to == principal.email &&
    resource.assignment_type == "record"
};
                """.strip(),
            },
            # Ground Truth Generation policies - Admin only
            {
                "id": "AdminGenerateGroundTruth",
                "statement": """
permit(
    principal in A360TranscriptionEvaluator::Group::"admin",
    action == A360TranscriptionEvaluator::Action::"GenerateGroundTruth",
    resource
);
                """.strip(),
            },
            # Brand Management policies - Admin only
            {
                "id": "AdminManageBrands",
                "statement": """
permit(
    principal in A360TranscriptionEvaluator::Group::"admin",
    action == A360TranscriptionEvaluator::Action::"ManageBrands",
    resource
);
                """.strip(),
            },
            {
                "id": "AdminViewBrands",
                "statement": """
permit(
    principal in A360TranscriptionEvaluator::Group::"admin",
    action == A360TranscriptionEvaluator::Action::"ViewBrands",
    resource
);
                """.strip(),
            },
            # Terms Management policies - Admin only
            {
                "id": "AdminManageTerms",
                "statement": """
permit(
    principal in A360TranscriptionEvaluator::Group::"admin",
    action == A360TranscriptionEvaluator::Action::"ManageTerms",
    resource
);
                """.strip(),
            },
            {
                "id": "AdminViewTerms",
                "statement": """
permit(
    principal in A360TranscriptionEvaluator::Group::"admin",
    action == A360TranscriptionEvaluator::Action::"ViewTerms",
    resource
);
                """.strip(),
            },
            # Job Management policies
            {
                "id": "AdminManageAllJobs",
                "statement": """
permit(
    principal in A360TranscriptionEvaluator::Group::"admin",
    action == A360TranscriptionEvaluator::Action::"ManageJobs",
    resource
);
                """.strip(),
            },
            {
                "id": "UserViewOwnJobs",
                "statement": """
permit(
    principal,
    action == A360TranscriptionEvaluator::Action::"ViewJobs",
    resource
) when {
    resource.user_id == principal.email
};
                """.strip(),
            },
            {
                "id": "AdminViewAllJobs",
                "statement": """
permit(
    principal in A360TranscriptionEvaluator::Group::"admin",
    action == A360TranscriptionEvaluator::Action::"ViewJobs",
    resource
);
                """.strip(),
            },
        ]

        for i, policy in enumerate(policies):
            avp.CfnPolicy(
                self,
                f"Policy{i + 1}",
                policy_store_id=policy_store.attr_policy_store_id,
                definition=avp.CfnPolicy.PolicyDefinitionProperty(
                    static=avp.CfnPolicy.StaticPolicyDefinitionProperty(
                        statement=policy["statement"],
                        description=f"RBAC policy: {policy['id']}",
                    )
                ),
            )

    def _create_lambda_triggers(self):
        """Create Lambda triggers for user lifecycle management."""

        # Pre-signup Lambda to prevent unauthorized registrations
        pre_signup_lambda = lambda_.Function(
            self,
            "PreSignupLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_inline("""
import json

def handler(event, context):
    # Only allow admin-created users
    if event['triggerSource'] == 'PreSignUp_AdminCreateUser':
        # Allow admin-created users
        return event
    else:
        # Reject self-registration
        raise Exception('Self-registration is not allowed')
            """),
            description="Pre-signup trigger to prevent self-registration",
            timeout=Duration.seconds(30),
        )

        # Post-confirmation Lambda to set up user profile
        post_confirmation_lambda = lambda_.Function(
            self,
            "PostConfirmationLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_inline("""
import json
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    try:
        # Log user confirmation for audit
        logger.info(f"User confirmed: {event['userName']}")
        
        # Here you could create initial user profile in RDS
        # or perform other post-confirmation tasks
        
        return event
        
    except Exception as e:
        logger.error(f"Post-confirmation error: {str(e)}")
        return event
            """),
            description="Post-confirmation trigger for user setup",
            timeout=Duration.seconds(30),
        )

        # Grant Lambda permissions to write logs
        pre_signup_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=["*"],
            )
        )

        post_confirmation_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=["*"],
            )
        )

        # Update user pool with new triggers
        cfn_user_pool = self.user_pool.node.default_child
        cfn_user_pool.lambda_config = {
            "PreSignUp": pre_signup_lambda.function_arn,
            "PostConfirmation": post_confirmation_lambda.function_arn,
        }

        # Grant Cognito permission to invoke Lambda functions
        pre_signup_lambda.add_permission(
            "CognitoInvokePermission",
            principal=iam.ServicePrincipal("cognito-idp.amazonaws.com"),
            source_arn=self.user_pool.user_pool_arn,
        )

        post_confirmation_lambda.add_permission(
            "CognitoInvokePermission",
            principal=iam.ServicePrincipal("cognito-idp.amazonaws.com"),
            source_arn=self.user_pool.user_pool_arn,
        )
