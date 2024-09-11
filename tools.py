import json
import ast
from constants import ModelIDs, Temperature, ToolConfig
from utils import FileUtility
from bedrock_util import BedrockUtils
from tool_error import ToolError

UNKNOWN_TYPE = "UNK"
DOCUMENT_TYPES = ["URLA", "W2", "PAY_STUB", "DRIVERS_LICENSE", UNKNOWN_TYPE]
TEMP_FOLDER = "temp"
class IDPTools:

    def __init__(self):
        
        sonnet_model_id = ModelIDs.anthropic_claude_3_sonnet
        haiku_model_id = ModelIDs.anthropic_claude_3_haiku
        
        self.temp_focused = Temperature.FOCUSED
        self.temp_balanced = Temperature.BALANCED
        
        self.sonnet_bedrock_utils = BedrockUtils(model_id=sonnet_model_id)
        self.haiku_bedrock_utils = BedrockUtils(model_id=haiku_model_id)

    def get_binary_for_file(self, file_path):
        binary_data = ""
        file_util = FileUtility()
        if file_path.endswith('.pdf'):
            binary_data = file_util.pdf_to_png_bytes(file_path)
            media_type = "png"
        elif file_path.endswith(('.jpeg', '.jpg', '.png')):
            binary_data, media_type = file_util.image_to_base64(file_path)
        else:
            print(f"Unsupported file type: {file_path}")
            binary_data, media_type = None
        return binary_data, media_type

    def get_tool_result(self, tool_use_block):
        tool_use_name = tool_use_block['name']
    
        print(f"Using tool {tool_use_name}")
        file_util = FileUtility(download_folder=TEMP_FOLDER)
        if tool_use_name == 'download_application_package':
            # Download file from S3
            file_path = file_util.unzip_from_s3(tool_use_block['input']['source_bucket']
                                                   , tool_use_block['input']['source_key'])
            return file_path
        elif tool_use_name == 'pdf_to_images':
            pdf_path = tool_use_block['input']['pdf_path']
            image_list = file_util.save_pdf_pages_as_png(pdf_path)
            return image_list
        elif tool_use_name == 'classify_documents':
            document_paths = tool_use_block['input']['document_paths']
            responses = self.categorize_document(document_paths)
            return responses
        elif tool_use_name == 'check_required_documents':
            classified_documents = tool_use_block['input']['classified_documents']
            responses = self.check_required_documents(classified_documents)
            return responses
        elif tool_use_name == 'reject_incomplete_application':
            missing_documents = tool_use_block['input']['missing_documents']
            responses = self.reject_incomplete_application(missing_documents)
            return responses
        elif tool_use_name == 'extract_urla_loan_info':
            print(tool_use_name)
            loan_info = tool_use_block['input']['loan_info']
            # Save data into DB here
            return [(json.dumps(loan_info))]
        elif tool_use_name == 'extract_urla_borrower_info':
            borrower_info = tool_use_block['input']['borrower_info']
            # Save data into DB here
            return [(json.dumps(borrower_info))]
        elif tool_use_name == 'extract_urla_employment_info':
            employment_info = tool_use_block['input']['employment_info']
            # Save data into DB here
            return [(json.dumps(employment_info))]
        elif tool_use_name == 'extract_urla_info':
            loan_info = tool_use_block['input']['loan_info']
            borrower_info = tool_use_block['input']['borrower_info']
            employment_info = tool_use_block['input']['employment_info']
            assets = tool_use_block['input']['assets']
            liabilities = tool_use_block['input']['liabilities']
            declarations = tool_use_block['input']['declarations']
            responses = self.extract_urla_info(loan_info, borrower_info, employment_info, assets, liabilities, declarations)
            return responses
        elif tool_use_name == 'extract_drivers_license_info':
            print(tool_use_block['input'])
            license_info = tool_use_block['input']['license_info']
            return license_info
        elif tool_use_name == 'extract_drivers_license_personal_info':
            print(tool_use_block['input'])
            personal_info = tool_use_block['input']['personal_info']
            return personal_info
        elif tool_use_name == 'extract_w2_information':
            w2_information = tool_use_block['input']['w2_information']
            responses = self.extract_w2_information(w2_information)
            return responses
        elif tool_use_name == 'stop_tool':
            stop_reason = tool_use_block['input']['stop_reason']
            print(json.dumps(stop_reason, indent=4))
            return
        else:
            raise ToolError(f"Invalid function name: {tool_use_name}")

    def categorize_document(self, file_paths):
        """
        Categorize documents based on their content.

        Args:
            file_paths (List[str]): List of file paths to process.

        Returns:
            List of categorization results.
        """
        
        try:
            if len(file_paths) == 1:
                # Single file handling
                binary_data, media_type = self.get_binary_for_file(file_paths[0])
                if binary_data is None or media_type is None:
                    return []
                
                message_content = [
                    {"image": {"format": media_type, "source": {"bytes": data}}}
                    for data in binary_data
                ]
            else:
                # Multiple file handling
                binary_data_array = []
                for file_path in file_paths:
                    binary_data, media_type = self.get_binary_for_file(file_path)
                    if binary_data is None or media_type is None:
                        continue
                    # Only use the first page for classification in multiple file case
                    binary_data_array.append((binary_data[0], media_type))

                if not binary_data_array:
                    return []

                message_content = [
                    {"image": {"format": media_type, "source": {"bytes": data}}}
                    for data, media_type in binary_data_array
                ]

            message_list = [{
                "role": 'user',
                "content": [
                    *message_content,
                    {"text": "What types of document is in this image?"}
                ]
            }]
            # print(json.dumps(file_paths, indent=4))
            system_message = [{
                "text": (
                            "<task>"
                                "You are a document processing agent and you have perfect vision. "
                                "Look through every image presented and categorize them based on the <doc_type_choices>. "
                                "The final output is a json array with an element for each image. "
                                "Each element in the output array contains the classified_doc_type and the file_path"  
                            "</task> "
                            f"<doc_type_choices>{', '.join(DOCUMENT_TYPES)}</doc_type_choices> "
                            "<output_format>"
                                "{'docs': [{'type':value_for_doc_type, 'file_paths': array__for_file_path}]}"
                            "</output_format>"
                            "In this case PS means pay stub, DL means driver's license, and UNK means unknown. "
                            "<important>"
                                "the output has to only be a json array in the <output_format> only. do not include anything else. "
                            "</important>"
                            f"<file_paths>{json.dumps(file_paths, indent=4)}</file_paths>"
                            "<example_output>"
                                "{"
                                  "'documents': ["
                                    "{"
                                      "'type': 'URLA',"
                                      "'files': ["
                                        "'example/1.png',"
                                        "'example/2.png',"
                                        "'example/3.png',"
                                      "]"
                                    "},"
                                    "{"
                                      "'type': 'DL',"
                                      "'files': ["
                                        "'example/4.png'"
                                      "]"
                                    "},"
                                    "{"
                                      "'type': 'W2"
                                      "'files': ["
                                        "'example/5.png'"
                                      "]"
                                    "}"
                                  "]"
                                "}"
                            "</example_output>"
                    )
            }]

            response = self.sonnet_bedrock_utils.invoke_bedrock(
                message_list=message_list,
                system_message=system_message
            )
            response_message = [response['output']['message']]
            return response_message

        except Exception as e:
            print(f"An error occurred: {str(e)}")
            return []

    def check_required_documents(self, classified_documents):
        # Check if classified_documents is a string
        if isinstance(classified_documents, str):
            try:
                # Attempt to parse the string as JSON
                classified_documents = json.loads(classified_documents)
            except json.JSONDecodeError:
                # If parsing fails, return an error message
                return ["Error: Invalid JSON string provided"]
    
        # Check if classified_documents is now a dictionary
        if not isinstance(classified_documents, dict):
            return ["Error: Input must be a JSON object (dictionary)"]
            
        # Extract keys and join them with commas
        keys_list = classified_documents.keys()
        doc_list = ', '.join(keys_list)

        print (f"doc list is {doc_list}")
        required_documents = ["URLA", "DRIVERS_LICENSE"]
        message_list = [
            {
                "role": 'user',
                "content": [
                    {"text": f"The loan application has the following documents: <doc_list>{doc_list}</doc_list>. Are all the required documents present?"}
                ]
            }
        ]
    
        system_message = [
            {
                "text": (
                    f"<required_documents>{', '.join(required_documents)}</required_documents>"
                    "<task>You are a mortgage agent with attention to detail. "
                    "Your main task is to verify if "
                    "all the documents required (check <required_documents>) for a "
                    "mortgage application are present. Pay close attention to <doc_list> and determine if the docs are present.</task> <output>only output a json array "
                    "of the missing document type</output>"
                )
            }
        ]
    
        response = self.haiku_bedrock_utils.invoke_bedrock(message_list=message_list, system_message=system_message)       
        return [response['output']['message']]

    def reject_incomplete_application(self, missing_documents):
        # print(json.dumps(missing_documents, indent=4))
        response_message = []
        missing_docs = ", ".join(missing_documents)
        message_list = [
            {
                "role": "user",
                "content": [
                    {"text": f"These documents are missing {missing_docs}. Write a note asking for additonal documentation?"}
                ]
            }
        ]
        system_message = [
            {"text": "<task>You are a mortgage agent. You main task is to write notes to user asking for missing documentation</task>"}
        ]
        
        response = self.haiku_bedrock_utils.invoke_bedrock(message_list=message_list, system_message=system_message)
        response_message.append(response['output']['message'])
        return [response_message]

    def extract_urla_info(self, loan_info, borrower_info, employment_info, assets, liabilities, declarations):
        self.print_urla_info(loan_info, borrower_info, employment_info, assets, liabilities, declarations)
        # You would typically process and save the data here
        # For now, we'll just return the borrower information
        return {
            "borrower_info": borrower_info,
        }

    def extract_drivers_license_information(self, license_info, personal_info):
        # Print the personal info
        print("Personal Information:")
        print(personal_info)
    
        # Process and combine all the information
        extracted_data = {
            "license_info": license_info,
            "personal_info": personal_info,
        }
    
        # You can add any additional processing or validation here
    
        # Return the extracted and processed data
        return extracted_data

    def extract_w2_information(self, license_info, personal_info, physical_characteristics, restrictions_endorsements, additional_info):
        # Print the personal info
        print("Personal Information:")
        print(personal_info)
    
        # Process and combine all the information
        extracted_data = {
            "license_info": license_info,
            "personal_info": personal_info,
        }
    
        # You can add any additional processing or validation here
    
        # Return the extracted and processed data
        return extracted_data
 
    def extract_w2_information(self, w2_information):
        print("w2_information:")
        print(w2_information)
        return w2_information
    
    def print_urla_info(self, loan_info, borrower_info, employment_info, assets, liabilities, declarations):
        # Process loan information
        print("Loan information:")
        if loan_info:
            print(f"  Loan Amount: ${loan_info.get('loan_amount', 'N/A')}")
            print(f"  Loan Purpose: {loan_info.get('loan_purpose', 'N/A')}")
            print(f"  Property Address: {loan_info.get('property_address', 'N/A')}")
            print(f"  Property Value: ${loan_info.get('property_value', 'N/A')}")
        else:
            print("  No loan information provided")
    
        # Process borrower information
        print("\nBorrower information:")
        if borrower_info:
            print(f"  Name: {borrower_info.get('name', 'N/A')}")
            print(f"  SSN: {borrower_info.get('ssn', 'N/A')}")
            print(f"  DOB: {borrower_info.get('dob', 'N/A')}")
            print(f"  Citizenship: {borrower_info.get('citizenship', 'N/A')}")
            print(f"  Marital Status: {borrower_info.get('marital_status', 'N/A')}")
            print(f"  Dependents: {borrower_info.get('dependents', 'N/A')}")
            print(f"  Current Address: {borrower_info.get('current_address', 'N/A')}")
        else:
            print("  No borrower information provided")
    
        # Process employment information
        print("\nEmployment information:")
        if employment_info:
            print(f"  Employer Name: {employment_info.get('employer_name', 'N/A')}")
            print(f"  Position: {employment_info.get('position', 'N/A')}")
            print(f"  Start Date: {employment_info.get('start_date', 'N/A')}")
            print(f"  Monthly Income: ${employment_info.get('monthly_income', 'N/A')}")
        else:
            print("  No employment information provided")
    
        # Process asset information
        print("\nAsset information:")
        if assets:
            for asset in assets:
                print(f"  Account Type: {asset.get('account_type', 'N/A')}")
                print(f"  Financial Institution: {asset.get('financial_institution', 'N/A')}")
                print(f"  Account Number: {asset.get('account_number', 'N/A')}")
                print(f"  Cash Value: ${asset.get('cash_value', 'N/A')}")
                print("  ---")
        else:
            print("  No asset information provided")
    
        # Process liability information
        print("\nLiability information:")
        if liabilities:
            for liability in liabilities:
                print(f"  Account Type: {liability.get('account_type', 'N/A')}")
                print(f"  Company Name: {liability.get('company_name', 'N/A')}")
                print(f"  Account Number: {liability.get('account_number', 'N/A')}")
                print(f"  Unpaid Balance: ${liability.get('unpaid_balance', 'N/A')}")
                print(f"  Monthly Payment: ${liability.get('monthly_payment', 'N/A')}")
                print("  ---")
        else:
            print("  No liability information provided")
    
        # Process declarations
        print("\nDeclarations:")
        if declarations:
            print(f"  Bankruptcy: {declarations.get('bankruptcy', 'N/A')}")
            print(f"  Foreclosure: {declarations.get('foreclosure', 'N/A')}")
            print(f"  Lawsuit: {declarations.get('lawsuit', 'N/A')}")
            print(f"  Federal Debt: {declarations.get('federal_debt', 'N/A')}")
        else:
            print("  No declarations provided")
    
        print("\nURLA information processing complete.")
