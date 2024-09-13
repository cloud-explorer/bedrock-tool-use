import json
from constants import ModelIDs, Temperature
from utils import FileUtility
from bedrock_util import BedrockUtils
from tool_error import ToolError
from datetime import datetime

file_util = FileUtility()
UNKNOWN_TYPE = "UNK"
DOCUMENT_TYPES = ["URLA", "DRIVERS_LICENSE", UNKNOWN_TYPE]
TEMP_FOLDER = file_util.generate_temp_folder_name(5)


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
        
        if file_path.endswith('.pdf'):
            binary_data = file_util.pdf_to_png_bytes(file_path)
            media_type = "png"
        elif file_path.endswith(('.jpeg', '.jpg', '.png')):
            binary_data, media_type = file_util.image_to_base64(file_path)
        else:
            print(f"Unsupported file type: {file_path}")
            binary_data, media_type = None, None
        return binary_data, media_type

    def get_tool_result(self, tool_use_block):
        """
        Main function to route tool requests to appropriate handlers.
        """
        tool_use_name = tool_use_block['name']
        tool_functions = {
            'download_application_package': self.download_application_package,
            'pdf_to_images': self.pdf_to_images,
            'classify_documents': self.classify_documents,
            'check_required_documents': self.check_required_documents,
            'reject_incomplete_application': self.reject_incomplete_application,
            'extract_urla_loan_info': self.extract_urla_loan_info,
            'save_urla_loan_info': self.save_urla_loan_info,
            'extract_urla_borrower_info': self.extract_urla_borrower_info,
            'save_urla_borrower_info': self.save_urla_borrower_info,
            'extract_drivers_info': self.extract_drivers_info,
            'save_drivers_info': self.save_drivers_info,
            'verify_applicant_info': self.verify_applicant_info,
            'clean_up_tool': self.clean_up_tool
        }

        if tool_use_name not in tool_functions:
            raise ToolError(f"Invalid function name: {tool_use_name}")

        return tool_functions[tool_use_name](tool_use_block['input'])

    # Individual tool functions

    def download_application_package(self, input_data):
        """Download file from S3"""
        temp_file_path = file_util.unzip_from_s3(input_data['source_bucket'], input_data['source_key'])
        return [temp_file_path]

    def pdf_to_images(self, input_data):
        """Convert PDF to images"""
        print(input_data['pdf_path'])
        return file_util.save_pdf_pages_as_png(input_data['pdf_path'])

    def classify_documents(self, input_data):
        """Classify documents"""
        return self.categorize_document(input_data['document_paths'])

    def check_required_documents(self, input_data):
        """Check for required documents"""
        return self._check_required_documents(input_data['classified_documents'])

    def reject_incomplete_application(self, input_data):
        """Reject incomplete application"""
        return self._reject_incomplete_application(input_data['missing_documents'])

    def extract_urla_loan_info(self, input_data):
        """Extract URLA loan information"""
        return self.extract_info(input_data['urla_document_paths'], 5, 9)

    def save_urla_loan_info(self, input_data):
        """Save URLA loan information"""
        return {
            "status": True,
            "loan_info": input_data['loan_info'],
        }

    def extract_urla_borrower_info(self, input_data):
        """Extract URLA borrower information"""
        return self.extract_info(input_data['urla_document_paths'], 1, 9)

    def save_urla_borrower_info(self, input_data):
        """Save URLA borrower information"""
        return {
            "status": True,
            "borrower_info": input_data['borrower_info'],
        }

    def extract_drivers_info(self, input_data):
        """Extract driver's license information"""
        return self.extract_info(input_data['dl_document_paths'], 1, 1)

    def save_drivers_info(self, input_data):
        """Save driver's license information"""
        return {
            "status": True,
            "license_info": input_data['license_info']
        }

    def verify_applicant_info(self, input_data):
        """Compare and detect matches between the URLA (Uniform Residential Loan Application) 
        and Driver's License information."""
        borrower_info = input_data['borrower_info']
        license_info = input_data['license_info']
        return self.detect_match(borrower_info, license_info)

    def clean_up_tool(self, input_data):
        """Clean up temporary files"""
        temp_folder_path = input_data['temp_folder_path']
        file_util.delete_folder(temp_folder_path)
        return

    # Helper methods

    def categorize_document(self, file_paths):
        """
        Categorize documents based on their content.
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
            
            # Create system message with instructions
            data = {"file_paths": file_paths}
            files = json.dumps(data, indent=2)
            system_message = self._create_system_message(files)

            response = self.sonnet_3_5_bedrock_utils.invoke_bedrock(
                message_list=message_list,
                system_message=system_message
            )
            response_message = [response['output']['message']]
            return response_message

        except Exception as e:
            print(f"An error occurred: {str(e)}")
            return []

    def _check_required_documents(self, classified_documents):
        """
        Check if all required documents are present.
        """
        if isinstance(classified_documents, str):
            try:
                classified_documents = json.loads(classified_documents)
            except json.JSONDecodeError:
                return ["Error: Invalid JSON string provided"]
    
        if not isinstance(classified_documents, dict):
            return ["Error: Input must be a JSON object (dictionary)"]
            
        keys_list = classified_documents.keys()
        doc_list = ', '.join(keys_list)

        print(f"doc list is {doc_list}")
        required_documents = ["URLA", "DRIVERS_LICENSE"]

        missing_documents = [doc for doc in required_documents if doc not in keys_list]
        
        if not missing_documents:
            print("All required documents are present.")
            return []
        else:
            print(f"Missing documents: {', '.join(missing_documents)}")
            return missing_documents

    def _reject_incomplete_application(self, missing_documents):
        """
        Generate a rejection message for incomplete applications.
        """
        missing_docs = ", ".join(missing_documents)
        message_list = [
            {
                "role": "user",
                "content": [
                    {"text": f"These documents are missing {missing_docs}. Write a note asking for additional documentation?"}
                ]
            }
        ]
        system_message = [
            {"text": "<task>You are a mortgage agent. Your main task is to write notes to users asking for missing documentation</task>"}
        ]
        
        response = self.haiku_bedrock_utils.invoke_bedrock(message_list=message_list, system_message=system_message)
        return [response['output']['message']]

    def extract_info(self, file_paths, page_num, max_page):
        """
        Extract information from a specific page of a document.
        """
        if len(file_paths) != max_page:
            raise ValueError(f"Expected {max_page} file paths, but got {len(file_paths)}")
        if page_num > max_page or page_num <= 0:
            raise ValueError(f"Expected page_num to be between 1 and {max_page}, but got {page_num}")
        
        info_page_path = file_paths[page_num-1]
        binary_data, media_type = self.get_binary_for_file(info_page_path)
        
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
                {"text": "Extract information from this file"}
            ]
        }]
        system_message = [
            {"text": '''<task>
                            You are a mortgage agent. 
                            You have perfect vision. 
                            You read every field in the document presented to you and make association to the main entities on the document
                        </task>'''}
        ]
        response = self.haiku_bedrock_utils.invoke_bedrock(message_list=message_list, 
                                                           system_message=system_message)       
        return [response['output']['message']]

    def _create_system_message(self, files):
        """
        Create a system message for document classification.
        """
        return [{
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
                    </instructions>
                    
                    <important>
                    Do not include any text outside the JSON object in your response.
                    Your entire response should be parseable as a single JSON object.
                    </important>
                    '''
        }]

    def detect_match(self, borrower_info, license_info):
        # Initialize result dictionary
        result = {
            "matches": {
                "name": False,
                "dob": False,
                "address": False
            },
            "discrepancies": [],
            "match_score": 0
        }
    
        # Compare names
        urla_name = borrower_info['name'].lower().replace(' ', '')
        license_name = license_info['full_name'].lower().replace(' ', '')
        name_similarity = sum(a == b for a, b in zip(urla_name, license_name)) / max(len(urla_name), len(license_name))
        result['matches']['name'] = name_similarity >= 0.9
        if not result['matches']['name']:
            result['discrepancies'].append("Name")
    
        # Compare dates of birth
        try:
            urla_dob = datetime.strptime(borrower_info['dob'], "%Y-%m-%d")
            license_dob = datetime.strptime(license_info['date_of_birth'], "%Y-%m-%d")
            result['matches']['dob'] = urla_dob == license_dob
            if not result['matches']['dob']:
                result['discrepancies'].append("Date of Birth")
        except ValueError:
            result['discrepancies'].append("Date of Birth (Invalid format)")
    
        # Compare addresses
        urla_address = borrower_info['current_address'].lower().replace(' ', '')
        license_address = license_info['address'].lower().replace(' ', '')
        address_similarity = sum(a == b for a, b in zip(urla_address, license_address)) / max(len(urla_address), len(license_address))
        result['matches']['address'] = address_similarity >= 0.9
        if not result['matches']['address']:
            result['discrepancies'].append("Address")
    
        # Calculate overall match score
        result['match_score'] = (
            (name_similarity * 40) +  # Name is weighted 40%
            (result['matches']['dob'] * 30) +  # DoB is weighted 30%
            (address_similarity * 30)  # Address is weighted 30%
        )
    
        return result