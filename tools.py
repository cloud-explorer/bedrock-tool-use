import json
import ast
from constants import ModelIDs, Temperature, ToolConfig
from utils import FileUtility
from bedrock_util import BedrockUtils
from tool_error import ToolError

UNKNOWN_TYPE = "UNK"
DOCUMENT_TYPES = ["URLA", "DRIVERS_LICENSE", UNKNOWN_TYPE]
TEMP_FOLDER = "temp"
class IDPTools:

    def __init__(self):
        
        sonnet_model_id = ModelIDs.anthropic_claude_3_sonnet
        haiku_model_id = ModelIDs.anthropic_claude_3_haiku
        sonnet35_model_id = ModelIDs.anthropic_claude_3_5_sonnet
        
        self.temp_focused = Temperature.FOCUSED
        self.temp_balanced = Temperature.BALANCED
        
        self.sonnet_3_bedrock_utils = BedrockUtils(model_id=sonnet_model_id)
        self.haiku_bedrock_utils = BedrockUtils(model_id=haiku_model_id)
        self.sonnet_3_5_bedrock_utils = BedrockUtils(model_id=sonnet35_model_id)

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
            # loan_info = tool_use_block['input']['loan_info']
            # print(loan_info)
            # Save data into DB here
            # return [(json.dumps(loan_info))]
            urla_document_paths = tool_use_block['input']['urla_document_paths']
            return self.extract_urla_loan_info(urla_document_paths)
        elif tool_use_name == 'save_urla_loan_info':
            loan_info = tool_use_block['input']['loan_info']
            print(loan_info)
            # Save data into DB here
            # return [(json.dumps(loan_info))]
            #urla_document_paths = tool_use_block['input']['urla_document_paths']
            #return self.extract_urla_loan_info(urla_document_paths)
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
            # Create a dictionary with "file_paths" as the key and the array of paths as the value
            data = {"file_paths": file_paths}
            # Convert the dictionary to a JSON string
            files = json.dumps(data, indent=2)
            system_message = [{
                "text": f'''
                        <task>
                        You are a document processing agent. You have perfect vision. You meticulously analyze the images and categorize them based on these document types:
                        <document_types>{DOCUMENT_TYPES}</document_types>
                        </task>
                        
                        <input_files>
                        {files}
                        </input_files>
                        
                        <instructions>
                        1. Categorize each file into one of the document types.
                        2. Group files of the same type together.
                        3. Use 'UNK' for unknown document types.
                        4. Respond ONLY with a JSON object in the specified format.
                        </instructions>
                        
                        <output_format>
                        {{
                          "documents": [
                            {{
                              "type": "DOCUMENT_TYPE",
                              "files": ["file_path1", "file_path2", ...]
                            }},
                            ...
                          ]
                        }}
                        </output_format>
                        
                        <examples>
                            <example1>
                            {{
                              "documents": [
                                {{
                                  "type": "URLA",
                                  "files": ["example/1.png", "example/2.png", "example/3.png"]
                                }},
                                {{
                                  "type": "DRIVERS_LICENSE",
                                  "files": ["example/4.png"]
                                }}
                              ]
                            }}
                            </example1>
                            
                            <example2>
                            {{
                              "documents": [
                                {{
                                  "type": "DRIVERS_LICENSE",
                                  "files": ["example/5.png"]
                                }}
                              ]
                            }}
                            </example2>
                        </examples>
                        
                        <important>
                        Do not include any text outside the JSON object in your response.
                        Your entire response should be parseable as a single JSON object.
                        </important>
                        '''
            }]

            response = self.sonnet_3_5_bedrock_utils.invoke_bedrock(
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

        # Check if all required documents are in keys_list
        all_present = all(doc in keys_list for doc in required_documents)
        
        # Find missing documents, if any
        missing_documents = [doc for doc in required_documents if doc not in keys_list]
        
        if all_present:
            print("All required documents are present.")
            return []
        else:
            print(f"Missing documents: {', '.join(missing_documents)}")
            return missing_documents


        ######################################
        # TODO: 
        # Code below here will not be hit
        # Code left behind just for reference. 
        # Should be deleted later
        ######################################
        message_list = [
            {
                "role": 'user',
                "content": [
                    {"text": f'''
                            <available_docs>{doc_list}</available_docs>
                            <required_documents>{required_documents}</required_documents>
                            
                            Please analyze the documents in <available_docs> against the <required_documents> and determine if any required documents are missing.
                            '''}
                ]
            }
        ]
        print 
        system_message = [
            {
                "text": f'''
                            <required_documents>{', '.join(required_documents)}</required_documents>

                            <task>
                            You are a meticulous mortgage agent with exceptional attention to detail. Your primary responsibility is to verify the completeness of a mortgage application by ensuring all required documents are present.

                            1. Carefully review the list of required documents in <required_documents>.
                            2. Examine the provided <available_docs> thoroughly.
                            3. Identify any required documents that are missing from the <doc_list>.
                            4. Compile a list of missing document types.
                            </task>
                            
                            <instructions>
                            1. Compare each item in <required_documents> against the <doc_list>.
                            2. If a required document is not found in <available_docs>, consider it missing.
                            3. Be precise in your assessment, avoiding false positives or negatives.
                            4. Use exact document type names as specified in <required_documents>.
                            </instructions>
                            
                            <output_format>
                            Provide only a JSON array containing the missing document types. 
                            Example: ["URLA", "DRIVERS_LICENSE"]
                            If no documents are missing, return an empty array: []
                            </output_format>
                            
                            <important>
                            Your response must strictly adhere to the specified JSON array format. Do not include any explanations, additional text, or formatting outside of the JSON array.
                            </important>
                            '''
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

    def extract_urla_loan_info(self, file_paths):
        
        print (file_paths)
        file_paths = file_paths['URLA']['file_paths']
        # Check if there are exactly 9 pages in the URLS
        if len(file_paths) != 9:
            raise ValueError(f"Expected 9 file paths, but got {len(file_paths)}")
    
        # Get the 5th element. This is the page with the loan info
        loan_page_path = file_paths[4]

        # Single file handling
        binary_data, media_type = self.get_binary_for_file(loan_page_path)
        if binary_data is None or media_type is None:
            return []
        
        message_content = [
            {"image": {"format": media_type, "source": {"bytes": data}}}
            for data in binary_data
        ]

        message_list = [{
                "role": 'user',
                "content": [
                    *message_content,
                    {"text": "extract information from this file?"}
                ]
            }]
        response = self.haiku_bedrock_utils.invoke_bedrock(message_list=message_list)       
        return [response['output']['message']]
        
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
