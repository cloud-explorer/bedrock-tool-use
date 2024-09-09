class ModelIDs:
    ai21_j1_jumbo_instruct = "ai21.j-jumbo-instruct-v1:0"
    ai21_j2_mid = "ai21.j2-mid-v1"
    ai21_j2_ultra = "ai21.j2-ultra-v1"
    amazon_titan_text_express = "amazon.titan-text-express-v1"
    amazon_titan_text_lite = "amazon.titan-text-lite-v1"
    amazon_titan_text_premium = "amazon.titan-text-premium-v1:0"
    amazon_titan_embed_text = "amazon.titan-embed-text-v1"
    amazon_titan_embed_text_v2 = "amazon.titan-embed-text-v2:0"
    amazon_titan_embed_image = "amazon.titan-embed-image-v1"
    amazon_titan_image_generator = "amazon.titan-image-generator-v1"
    amazon_titan_image_generator_v2 = "amazon.titan-image-generator-v2:0"
    anthropic_claude_v2 = "anthropic.claude-v2"
    anthropic_claude_v2_1 = "anthropic.claude-v2:1"
    anthropic_claude_3_sonnet = "anthropic.claude-3-sonnet-20240229-v1:0"
    anthropic_claude_3_opus = "anthropic.claude-3-opus-20240229-v1:0"
    anthropic_claude_3_haiku = "anthropic.claude-3-haiku-20240307-v1:0"
    anthropic_claude_instant = "anthropic.claude-instant-v1"
    cohere_command = "cohere.command-text-v14"
    cohere_command_light = "cohere.command-light-text-v14"
    cohere_command_nightly = "cohere.command-v1:0"
    cohere_command_v14 = "cohere.command-v14-v1:0"
    cohere_embed_english = "cohere.embed-english-v3"
    cohere_embed_multilingual = "cohere.embed-multilingual-v3"
    meta_llama2_13b_chat = "meta.llama2-13b-chat-v1"
    meta_llama2_70b_chat = "meta.llama2-70b-chat-v1"
    meta_llama3_8b_instruct = "meta.llama3-8b-instruct-v1:0"
    meta_llama3_70b_instruct = "meta.llama3-70b-instruct-v1:0"
    meta_llama3_7b_instruct = "meta.llama3-7-70b-instruct-v1:0"
    meta_llama3_14b_instruct = "meta.llama3-1-40b-instruct-v1:0"
    mistral_7b_instruct = "mistral.mistral-7b-instruct-v0:2"
    mistral_8x7b_instruct = "mistral.mistral-8x7b-instruct-v0:1"
    mistral_large = "mistral.mistral-large-2402-v1:0"
    mistral_large_latest = "mistral.mistral-large-2407-v1:0"
    mistral_small = "mistral.mistral-small-2402-v1:0"
    stability_stable_diffusion = "stability.stable-diffusion-xl-v0"
    stability_stable_diffusion_v1 = "stability.stable-diffusion-xl-v1"


class Temperature:
    FOCUSED = 0
    BALANCED = 0.3
    CREATIVE = 0.75
    EXPERIMENTAL = 1

class ToolConfig:
    COT = [
                {
                    "toolSpec": {
                        "name": "download_application_package",
                        "description": ("Downloads the file containing loan application documents from S3"
                                        ", extracts its content and returns a list of paths of extracted files, or None if extraction failed."),
                        "inputSchema": {
                            "json": {
                                "type": "object",
                                "properties": {
                                    "source_bucket": {
                                        "type": "string",
                                        "description": "The S3 bucket name where the zip file is stored."
                                    },
                                    "source_key": {
                                        "type": "string",
                                        "description": "The S3 key (path) of the zip file."
                                    },
                                    "target_folder": {
                                        "type": "string",
                                        "description": "Local folder where the zip file should be saved."
                                    }
                                },
                                "required": ["source_bucket", "source_key", "target_folder"]
                            }
                        }
                    }
                },
                {
                    "toolSpec": {
                        "name": "classify_documents",
                        "description": "Classify the documents in the loan application package.",
                        "inputSchema": {
                            "json": {
                                "type": "object",
                                "properties": {
                                    "document_paths": {
                                        "type": "array",
                                        "items": {
                                            "type": "string"
                                        },
                                        "description": "List of paths to the extracted documents."
                                    }
                                },
                                "required": ["document_paths"]
                            }
                        }
                    }
                },
                {
                    "toolSpec": {
                        "name": "check_required_documents",
                        # "description": "Check if all required document types (URLA, Drivers License, W2, Paystub) are present.",
                        "description": "Check if all required document types (URLA, Drivers License) are present.",
                        "inputSchema": {
                            "json": {
                                "type": "object",
                                "properties": {
                                    "classified_documents": {
                                        "type": "object",
                                        "description": "Dictionary of document types and their corresponding file paths."
                                    }
                                },
                                "required": ["classified_documents"]
                            }
                        }
                    }
                },
                {
                    "toolSpec": {
                        "name": "reject_incomplete_application",
                        "description": "Reject the loan application if required documents are missing.",
                        "inputSchema": {
                            "json": {
                                "type": "object",
                                "properties": {
                                    "missing_documents": {
                                        "type": "array",
                                        "items": {
                                            "type": "string"
                                        },
                                        "description": "List of missing document types."
                                    }
                                },
                                "required": ["missing_documents"]
                            }
                        }
                    }
                },
                {
                    "toolSpec": {
                        "name": "extract_urla_info",
                        "description": "Extract important information from the Uniform Residential Loan Application (URLA) form.",
                        "inputSchema": {
                            "json": {
                                "type": "object",
                                "properties": {
                                    "loan_info": {
                                        "type": "object",
                                        "properties": {
                                            "loan_amount": {
                                                "type": "number",
                                                "description": "The loan amount requested"
                                            },
                                            "loan_purpose": {
                                                "type": "string",
                                                "enum": ["Purchase", "Refinance", "Other"],
                                                "description": "The purpose of the loan"
                                            },
                                            "property_address": {
                                                "type": "string",
                                                "description": "The full address of the property"
                                            },
                                            "property_value": {
                                                "type": "number",
                                                "description": "The value of the property"
                                            }
                                        },
                                        "required": ["loan_amount", "loan_purpose", "property_address"]
                                    },
                                    "borrower_info": {
                                        "type": "object",
                                        "properties": {
                                            "name": {
                                                "type": "string",
                                                "description": "Full name of the borrower"
                                            },
                                            "ssn": {
                                                "type": "string",
                                                "description": "Social Security Number of the borrower"
                                            },
                                            "dob": {
                                                "type": "string",
                                                "description": "Date of birth of the borrower"
                                            },
                                            "citizenship": {
                                                "type": "string",
                                                "enum": ["U.S. Citizen", "Permanent Resident Alien", "Non-Permanent Resident Alien"],
                                                "description": "Citizenship status of the borrower"
                                            },
                                            "marital_status": {
                                                "type": "string",
                                                "enum": ["Married", "Separated", "Unmarried"],
                                                "description": "Marital status of the borrower"
                                            },
                                            "dependents": {
                                                "type": "number",
                                                "description": "Number of dependents"
                                            },
                                            "current_address": {
                                                "type": "string",
                                                "description": "Current address of the borrower"
                                            }
                                        },
                                        "required": ["name", "ssn", "dob", "citizenship", "marital_status", "current_address"]
                                    },
                                    "employment_info": {
                                        "type": "object",
                                        "properties": {
                                            "employer_name": {
                                                "type": "string",
                                                "description": "Name of the current employer"
                                            },
                                            "position": {
                                                "type": "string",
                                                "description": "Current job position or title"
                                            },
                                            "start_date": {
                                                "type": "string",
                                                "description": "Start date of current employment"
                                            },
                                            "monthly_income": {
                                                "type": "number",
                                                "description": "Total monthly income"
                                            }
                                        },
                                        "required": ["employer_name", "position", "start_date", "monthly_income"]
                                    },
                                    "assets": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "account_type": {
                                                    "type": "string",
                                                    "description": "Type of asset account"
                                                },
                                                "financial_institution": {
                                                    "type": "string",
                                                    "description": "Name of the financial institution"
                                                },
                                                "account_number": {
                                                    "type": "string",
                                                    "description": "Account number"
                                                },
                                                "cash_value": {
                                                    "type": "number",
                                                    "description": "Cash or market value of the asset"
                                                }
                                            },
                                            "required": ["account_type", "financial_institution", "account_number", "cash_value"]
                                        }
                                    },
                                    "liabilities": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "account_type": {
                                                    "type": "string",
                                                    "description": "Type of liability account"
                                                },
                                                "company_name": {
                                                    "type": "string",
                                                    "description": "Name of the company or creditor"
                                                },
                                                "account_number": {
                                                    "type": "string",
                                                    "description": "Account number"
                                                },
                                                "unpaid_balance": {
                                                    "type": "number",
                                                    "description": "Unpaid balance on the liability"
                                                },
                                                "monthly_payment": {
                                                    "type": "number",
                                                    "description": "Monthly payment amount"
                                                }
                                            },
                                            "required": ["account_type", "company_name", "account_number", "unpaid_balance", "monthly_payment"]
                                        }
                                    },
                                    "declarations": {
                                        "type": "object",
                                        "properties": {
                                            "bankruptcy": {
                                                "type": "boolean",
                                                "description": "Whether the borrower has declared bankruptcy in the past 7 years"
                                            },
                                            "foreclosure": {
                                                "type": "boolean",
                                                "description": "Whether the borrower has had a property foreclosed upon in the last 7 years"
                                            },
                                            "lawsuit": {
                                                "type": "boolean",
                                                "description": "Whether the borrower is a party to a lawsuit"
                                            },
                                            "federal_debt": {
                                                "type": "boolean",
                                                "description": "Whether the borrower is delinquent or in default on a Federal debt"
                                            }
                                        },
                                        "required": ["bankruptcy", "foreclosure", "lawsuit", "federal_debt"]
                                    }
                                },
                                "required": ["loan_info", "borrower_info", "employment_info", "assets", "liabilities", "declarations"]
                            }
                        }
                    }
                },
                {
                    "toolSpec": {
                        "name": "extract_drivers_license_information",
                        "description": "Extract important information from a driver's license. Double check the information before generating result and make sure the output is a valid json",
                        "inputSchema": {
                            "json": {
                                "type": "object",
                                "properties": {
                                    "license_info": {
                                        "type": "object",
                                        "properties": {
                                            "license_number": {
                                                "type": "string",
                                                "description": "The driver's license number"
                                            },
                                            "class": {
                                                "type": "string",
                                                "description": "The class of the driver's license"
                                            },
                                            "state": {
                                                "type": "string",
                                                "description": "The state that issued the license"
                                            },
                                            "issue_date": {
                                                "type": "string",
                                                "description": "The date the license was issued"
                                            },
                                            "expiration_date": {
                                                "type": "string",
                                                "description": "The date the license expires"
                                            }
                                        },
                                        "required": ["license_number", "class", "state", "issue_date", "expiration_date"]
                                    },
                                    "personal_info": {
                                        "type": "object",
                                        "properties": {
                                            "full_name": {
                                                "type": "string",
                                                "description": "Full name of the license holder"
                                            },
                                            "address": {
                                                "type": "string",
                                                "description": "Current address of the license holder"
                                            },
                                            "date_of_birth": {
                                                "type": "string",
                                                "description": "Date of birth of the license holder"
                                            },
                                            "sex": {
                                                "type": "string",
                                                "enum": ["M", "F", "X"],
                                                "description": "Sex of the license holder"
                                            }
                                        },
                                        "required": ["full_name", "address", "date_of_birth", "sex"]
                                    }
                                },
                                "required": ["license_info", "personal_info"]
                            }
                        }
                    }
                },
                {
                    "toolSpec": {
                        "name": "extract_w2_information",
                        "description": "Extract important information from a W-2 Wage and Tax Statement form.",
                        "inputSchema": {
                            "json": {
                                "type": "object",
                                "properties": {
                                    "w2_information": {
                                        "type": "object",
                                        "properties": {
                                            "employee_info": {
                                                "type": "object",
                                                "properties": {
                                                    "name": {
                                                        "type": "string",
                                                        "description": "Full name of the employee"
                                                    },
                                                    "ssn": {
                                                        "type": "string",
                                                        "description": "Social Security Number of the employee"
                                                    },
                                                    "address": {
                                                        "type": "string",
                                                        "description": "Full address of the employee"
                                                    }
                                                },
                                                "required": ["name", "ssn", "address"]
                                            },
                                            "employer_info": {
                                                "type": "object",
                                                "properties": {
                                                    "name": {
                                                        "type": "string",
                                                        "description": "Name of the employer"
                                                    },
                                                    "ein": {
                                                        "type": "string",
                                                        "description": "Employer Identification Number"
                                                    },
                                                    "address": {
                                                        "type": "string",
                                                        "description": "Full address of the employer"
                                                    }
                                                },
                                                "required": ["name", "ein", "address"]
                                            },
                                            "wage_info": {
                                                "type": "object",
                                                "properties": {
                                                    "wages_tips_other_comp": {
                                                        "type": "number",
                                                        "description": "Wages, tips, and other compensation (Box 1)"
                                                    },
                                                    "federal_income_tax_withheld": {
                                                        "type": "number",
                                                        "description": "Federal income tax withheld (Box 2)"
                                                    },
                                                    "social_security_wages": {
                                                        "type": "number",
                                                        "description": "Social security wages (Box 3)"
                                                    },
                                                    "social_security_tax_withheld": {
                                                        "type": "number",
                                                        "description": "Social security tax withheld (Box 4)"
                                                    },
                                                    "medicare_wages_and_tips": {
                                                        "type": "number",
                                                        "description": "Medicare wages and tips (Box 5)"
                                                    },
                                                    "medicare_tax_withheld": {
                                                        "type": "number",
                                                        "description": "Medicare tax withheld (Box 6)"
                                                    }
                                                },
                                                "required": [
                                                    "wages_tips_other_comp", "federal_income_tax_withheld",
                                                    "social_security_wages", "social_security_tax_withheld",
                                                    "medicare_wages_and_tips", "medicare_tax_withheld"
                                                ]
                                            },
                                            "state_local_info": {
                                                "type": "object",
                                                "properties": {
                                                    "state": {
                                                        "type": "string",
                                                        "description": "State code"
                                                    },
                                                    "state_wages_tips": {
                                                        "type": "number",
                                                        "description": "State wages, tips, etc."
                                                    },
                                                    "state_income_tax": {
                                                        "type": "number",
                                                        "description": "State income tax withheld"
                                                    },
                                                    "locality_name": {
                                                        "type": "string",
                                                        "description": "Local name (if applicable)"
                                                    },
                                                    "local_wages_tips": {
                                                        "type": "number",
                                                        "description": "Local wages, tips, etc."
                                                    },
                                                    "local_income_tax": {
                                                        "type": "number",
                                                        "description": "Local income tax withheld"
                                                    }
                                                },
                                                "required": ["state", "state_wages_tips", "state_income_tax"]
                                            },
                                            "additional_info": {
                                                "type": "object",
                                                "properties": {
                                                    "allocated_tips": {
                                                        "type": "number",
                                                        "description": "Allocated tips (Box 8)"
                                                    },
                                                    "dependent_care_benefits": {
                                                        "type": "number",
                                                        "description": "Dependent care benefits (Box 10)"
                                                    },
                                                    "nonqualified_plans": {
                                                        "type": "number",
                                                        "description": "Nonqualified plans (Box 11)"
                                                    },
                                                    "year": {
                                                        "type": "string",
                                                        "description": "Tax year for which the W-2 is issued"
                                                    }
                                                }
                                            }
                                        },
                                        "required": ["employee_info", "employer_info", "wage_info", "state_local_info"]
                                    }
                                },
                                "required": ["w2_information"]
                            }
                        }
                    }
                },
                {
                    "toolSpec": {
                        "name": "stop_tool",
                        "description": "Call this tool if the previous tool use is the logical end of the loop or needes to be aborted",
                        "inputSchema": {
                            "json": {
                                "type": "object",
                                "properties": {
                                    "stop_reason": {
                                        "type": "string",
                                        "description": "Reason for why the loop was aborted or ended"
                                    }
                                },
                                "required": ["stop_Reason"]
                            }
                        }
                    }
                }
            ]


    URLA = tool_config = []