import json
import ast
from constants import ModelIDs, Temperature, ToolConfig
from utils import FileUtility
from bedrock_util import BedrockUtils
from tool_error import ToolError

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
            binary_data, media_type = None
        return binary_data, media_type

    def get_tool_result(self, tool_use_block):
        tool_use_name = tool_use_block['name']
        urla_max_pages = 9
        drivers_license_max_page = 1
        print(f"Using tool {tool_use_name}")
        print(f"using temp folder {TEMP_FOLDER}")
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
            urla_document_paths = tool_use_block['input']['urla_document_paths']
            # Loan information is on page 5
            page_num = 5
            return self.extract_info(urla_document_paths, page_num, urla_max_pages)
        elif tool_use_name == 'save_urla_loan_info':
            loan_info = tool_use_block['input']['loan_info']
            return {
                "status": True,
                "loan_info": loan_info,
                # "next_action": "extract_urla_borrower_info"
            }
        elif tool_use_name == 'extract_urla_borrower_info':
            file_paths = tool_use_block['input']['urla_document_paths']
            # Borrower information is on page 1
            page_num = 1
            return self.extract_info(file_paths, page_num, urla_max_pages)
        elif tool_use_name == 'save_urla_borrower_info':
            borrower_info = tool_use_block['input']['borrower_info']
            return {
                "status": True,
                "borrower_info": borrower_info,
                # "next_action": "extract_drivers_personal_info"
            }
        elif tool_use_name == 'extract_drivers_info':
            file_paths = tool_use_block['input']['dl_document_paths']
            # There is only one page
            page_num = 1
            return self.extract_info(file_paths, page_num, drivers_license_max_page)
        elif tool_use_name == 'save_drivers_info':
            license_info = tool_use_block['input']['license_info']
            return {
                "status": True,
                "license_info": license_info
            }
        elif tool_use_name == 'clean_up_tool':
            temp_folder = tool_use_block['input']['temp_folder_paths']
            print(f"Deleting folder {temp_folder}")
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

    def extract_info(self, file_paths, page_num, max_page):
        
        print(file_paths)
        # Check if there are exactly 9 pages in the URLS
        if len(file_paths) != max_page:
            raise ValueError(f"Expected {max_page} file paths, but got {len(file_paths)}")
        if page_num > max_page or page_num <= 0:
            raise ValueError(f"Expected page_num to be between 1 and {max_page}, but got {page_num}")
        # Get the right page. Since this is 1 based index, subtract 1 from the page_num 
        info_page_path = file_paths[page_num-1]

        # Single file handling
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