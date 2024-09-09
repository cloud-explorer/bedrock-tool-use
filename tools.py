import json
import ast
from constants import ModelIDs, Temperature, ToolConfig
from utils import FileUtility
from bedrock_util import BedrockUtils
from tool_error import ToolError

UNKNOWN_TYPE = "UNK"
DOCUMENT_TYPES = ["URLA", "W2", "PAY_STUB", "DRIVERS_LICENSE", UNKNOWN_TYPE]

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
        
        if tool_use_name == 'download_application_package':
            file_util = FileUtility(download_folder=tool_use_block['input']['target_folder'])
            # Download file from S3
            file_path = file_util.unzip_from_s3(tool_use_block['input']['source_bucket']
                                                   , tool_use_block['input']['source_key'])
            return file_path
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
        elif tool_use_name == 'extract_urla_info':
            loan_info = tool_use_block['input']['loan_info']
            borrower_info = tool_use_block['input']['borrower_info']
            employment_info = tool_use_block['input']['employment_info']
            assets = tool_use_block['input']['assets']
            liabilities = tool_use_block['input']['liabilities']
            declarations = tool_use_block['input']['declarations']
            responses = self.extract_urla_info(loan_info, borrower_info, employment_info, assets, liabilities, declarations)
            return responses
        elif tool_use_name == 'extract_drivers_license_information':
            print(tool_use_block['input'])
            license_info = tool_use_block['input']['license_info']
            personal_info = tool_use_block['input']['personal_info']
            responses = self.extract_drivers_license_information(license_info, personal_info)
            return responses
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
                    {"text": "What types of documents are in this document?"}
                ]
            }]

            system_message = [{
                "text": (
                    "<task>You are a document processing agent and you have perfect vision. "
                    "Look through every image presented and categorize them based on the doc_type_choices. "
                    "There might be multiple types of documents on a given image. "
                    "Look carefully to see what documents are there. Double check if needed. "
                    "Finally produce a combined list of all the types of documents attached. "
                    "Include the start and end page numbers from the document in the outpu</task> "
                    f"<doc_type_choices>{', '.join(DOCUMENT_TYPES)}</doc_type_choices> "
                    "<output_format>{'docs': [{'type':[doc_type], 'file_path': [file_path], "
                    "'start_page_number': [start_page_number], 'end_page_number':[end_page_number]}]}</output_format>"
                    "In this case PS means pay stub, DL means driver's license, and UNK means unknown. "
                    "<important>Include only the answer in the <output_format> and nothing else. "
                    "Double check if the start and end page numbers included in the output are the right document type</important>"
                )
            }]

            # print(json.dumps(system_message, indent=4))

            response = self.sonnet_bedrock_utils.invoke_bedrock(
                message_list=message_list,
                system_message=system_message
            )
            response_message = [response['output']['message']]
            # print("categorize_document output")
            # print(json.dumps(response_message, indent=4))
            return response_message

        except Exception as e:
            print(f"An error occurred: {str(e)}")
            return []

    def check_required_documents(self, classified_documents):
        response_message = []
        
        # Parse the input if it's a string
        if isinstance(classified_documents, str):
            try:
                classified_documents = json.loads(classified_documents)
            except json.JSONDecodeError:
                print("Error decoding input JSON")
                return ["Error occurred while processing input"]
    
        # Ensure classified_documents is a dictionary
        if not isinstance(classified_documents, dict):
            print("Input is not a valid dictionary")
            return ["Error: Invalid input format"]
    
        print(json.dumps(classified_documents, indent=4))
        
        # Extract keys and join them with commas
        keys_list = list(classified_documents.keys())
        doc_list = ', '.join(keys_list)
    
        # Use a constant for required documents
        REQUIRED_DOCUMENTS = ["URLA", "Driver's License"]
    
        # Map document types to their standardized names
        document_type_mapping = {
            "URLA": "URLA",
            "DRIVERS_LICENSE": "Driver's License",
            "W2": "W2"
        }
    
        # Check if required documents are present
        present_documents = [document_type_mapping.get(doc_type, doc_type) for doc_type in keys_list]
        missing_docs = [doc for doc in REQUIRED_DOCUMENTS if doc not in present_documents]
    
        if not missing_docs:
            return []  # All required documents are present
    
        message_list = [
            {
                "role": 'user',
                "content": [
                    {"text": f"The loan application has the following documents: {doc_list}. Are all the required documents present?"}
                ]
            }
        ]
    
        system_message = [
            {
                "text": (
                    f"<required_documents>{', '.join(REQUIRED_DOCUMENTS)}</required_documents>"
                    "<task>You are a mortgage agent. Your main task is to verify if "
                    "all the documents required (check <required_documents>) for a "
                    "mortgage application are present. Double check and triple check "
                    "the output if needed.</task> <output>only output a json array "
                    "of the missing document type</output>"
                )
            }
        ]
    
        try:
            response = self.haiku_bedrock_utils.invoke_bedrock(message_list=message_list, system_message=system_message)
            if 'output' in response and 'message' in response['output']:
                response_message.append(response['output']['message'])
            else:
                raise ValueError("Unexpected response format from Bedrock")
        except Exception as e:
            print(f"Error invoking Bedrock: {str(e)}")
            return missing_docs  # Return the missing docs we found earlier
    
        # Validate the response
        try:
            bedrock_missing_docs = json.loads(response_message[0])
            if not isinstance(bedrock_missing_docs, list):
                raise ValueError("Response is not a valid JSON array")
            # Ensure only valid document types are in the response
            bedrock_missing_docs = [doc for doc in bedrock_missing_docs if doc in REQUIRED_DOCUMENTS]
            
            # Combine our findings with Bedrock's response
            missing_docs = list(set(missing_docs + bedrock_missing_docs))
        except json.JSONDecodeError:
            print("Error decoding JSON response")
        except ValueError as ve:
            print(f"Invalid response format: {str(ve)}")
    
        return missing_docs

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
        return response_message

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
