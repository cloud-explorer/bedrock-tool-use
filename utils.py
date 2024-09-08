import os
import requests
import fitz
import base64
from PIL import Image
import io
import boto3
import zipfile
import mimetypes
import uuid
    
class FileUtility:
    """
    A utility class for handling file operations such as downloading, unzipping, and converting PDFs to base64 encoded PNGs.

    Usage examples:
    
    # Create a FileUtility instance
    file_util = FileUtility(download_folder="my_downloads")

    # Download file from URL
    file_path = file_util.download_from_url("https://example.com/sample.pdf")

    # Download file from S3
    s3_file_path = file_util.download_from_s3("my-bucket", "path/to/sample.pdf")

    # Unzip file from S3
    extracted_files = file_util.unzip_from_s3("my-bucket", "path/to/archive.zip", "extracted_folder")

    # Convert PDF to base64 encoded PNGs
    if file_path.endswith('.pdf'):
        base64_pngs = file_util.pdf_to_base64_pngs(file_path)
        print(f"Number of pages converted: {len(base64_pngs)}")
        print(f"First page base64 (truncated): {base64_pngs[0][:50]}...")
    """

    def __init__(self, download_folder="downloads"):
        """
        Initialize the FileUtility instance.

        Args:
            download_folder (str): The folder to store downloaded files. Defaults to "downloads".
        """
        self.download_folder = download_folder
        os.makedirs(self.download_folder, exist_ok=True)
        self.s3_client = boto3.client('s3')

    def download_from_url(self, url):
        """
        Download a file from a given URL.

        Args:
            url (str): The URL of the file to download.

        Returns:
            str: The local path of the downloaded file, or None if download failed.
        """
        response = requests.get(url)
        if response.status_code == 200:
            file_name = os.path.join(self.download_folder, url.split("/")[-1])
            with open(file_name, "wb") as file:
                file.write(response.content)
            return file_name
        else:
            print(f"Failed to download file from {url}")
            return None

    def download_from_s3(self, bucket_name, object_key):
        """
        Download a file from an S3 bucket.

        Args:
            bucket_name (str): The name of the S3 bucket.
            object_key (str): The object key (path) of the file in the S3 bucket.

        Returns:
            str: The local path of the downloaded file, or None if download failed.
        """
        local_path = os.path.join(self.download_folder, object_key.split("/")[-1])
        try:
            self.s3_client.download_file(bucket_name, object_key, local_path)
            return local_path
        except Exception as e:
            print(f"Failed to download file from S3: {str(e)}")
            return None

    def unzip_from_s3(self, bucket_name, object_key, extract_to=None, upload_extracted=False, delete_zip=True):
        """
        Download a file from S3, check if it's a zip file, and if so, extract its contents.
        If not a zip file, return the file as the only element in the list.
    
        Args:
            bucket_name (str): The name of the S3 bucket.
            object_key (str): The object key (path) of the file in the S3 bucket.
            extract_to (str): The directory to extract files to. If None, extracts to a subdirectory of download_folder.
            upload_extracted (bool): If True, upload extracted files back to S3. Defaults to False.
            delete_zip (bool): If True, delete the original zip file after extraction. Defaults to True.
    
        Returns:
            list: A list of paths of extracted files or the single file path if not a zip, or None if download failed.
        """
        file_path = self.download_from_s3(bucket_name, object_key)
        if not file_path:
            return None
    
        # Check if the file is a zip file
        mime_type, _ = mimetypes.guess_type(file_path)
        is_zip = mime_type == 'application/zip' or file_path.lower().endswith('.zip')
    
        if not is_zip:
            print(f"Downloaded file is not a zip file: {file_path}")
            return [file_path]
    
        if extract_to is None:
            extract_to = os.path.join(self.download_folder, 'extracted_' + os.path.splitext(os.path.basename(file_path))[0])
    
        os.makedirs(extract_to, exist_ok=True)
    
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
    
            extracted_files = []
            for root, _, files in os.walk(extract_to):
                for file in files:
                    file_path = os.path.join(root, file)
                    extracted_files.append(file_path)
                    if upload_extracted:
                        s3_key = os.path.relpath(file_path, extract_to)
                        self.s3_client.upload_file(file_path, bucket_name, s3_key)
    
            if delete_zip:
                try:
                    os.remove(file_path)
                    print(f"Deleted local zip file: {file_path}")
                except Exception as e:
                    print(f"Failed to delete local zip file: {file_path}")
            return extracted_files
        except Exception as e:
            print(f"Failed to process file: {str(e)}")
            return [file_path]  # Return the original file if extraction fails

    def pdf_to_png_bytes(self, pdf_path, quality=75, max_size=(1024, 1024)):
        """
        Convert a PDF to an array of PNG image bytes.

        Args:
            pdf_path (str): The path to the PDF file.
            quality (int): The quality of the PNG images (1-95). Defaults to 75.
            max_size (tuple): The maximum width and height of the images. Defaults to (1024, 1024).
    
        Returns:
            list: An array of PNG image bytes, one for each page of the PDF.
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"The file {pdf_path} does not exist.")
    
        if not os.access(pdf_path, os.R_OK):
            raise IOError(f"The file {pdf_path} is not readable.")
            
        doc = fitz.open(pdf_path)
        png_bytes_array = []
        temp_folder = 'temp'
        
        os.makedirs(temp_folder, exist_ok=True)
    
        try:
            for page_num in range(doc.page_count):
                page = doc.load_page(page_num)
                pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
                image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    
                if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
                    image.thumbnail(max_size, Image.Resampling.LANCZOS)
    
                temp_file = os.path.join(temp_folder, f"{uuid.uuid4()}.png")
                image.save(temp_file, format='PNG', optimize=True, quality=quality)
    
                with open(temp_file, 'rb') as f:
                    png_bytes_array.append(f.read())
    
                os.remove(temp_file)
    
        finally:
            doc.close()
            os.rmdir(temp_folder)
    
        return png_bytes_array

    def pdf_to_jpg_bytes(self, pdf_path, quality=75, max_size=(1024, 1024)):
        """
        Convert a PDF to an array of JPG image bytes.
    
        Args:
            pdf_path (str): The path to the PDF file.
            quality (int): The quality of the JPG images (1-95). Defaults to 75.
            max_size (tuple): The maximum width and height of the images. Defaults to (1024, 1024).
    
        Returns:
            list: An array of JPG image bytes, one for each page of the PDF.
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"The file {pdf_path} does not exist.")
    
        if not os.access(pdf_path, os.R_OK):
            raise IOError(f"The file {pdf_path} is not readable.")
        
        doc = fitz.open(pdf_path)
        jpg_bytes_array = []
        temp_folder = 'temp'
        
        os.makedirs(temp_folder, exist_ok=True)

        try:
            for page_num in range(doc.page_count):
                page = doc.load_page(page_num)
                pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
                image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
                if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
                    image.thumbnail(max_size, Image.Resampling.LANCZOS)
    
                temp_file = os.path.join(temp_folder, f"{uuid.uuid4()}.jpeg")
                image.save(temp_file, format='JPEG', optimize=True, quality=quality)
    
                with open(temp_file, 'rb') as f:
                    jpg_bytes = f.read()
                    jpg_bytes_array.append(jpg_bytes)
                os.remove(temp_file)
        finally:
            doc.close()
            os.rmdir(temp_folder)
            
        return jpg_bytes_array

    
    def image_to_base64(self, file_path):
        """
        Convert an image file to binary data and determine its media type.
    
        Args:
            file_path (str): Path to the image file.
    
        Returns:
            tuple: (bytes_array, media_type)
                bytes_array (list): List containing the binary data of the image.
                media_type (str): MIME type of the image file based on its extension.
    
        Raises:
            FileNotFoundError: If the file does not exist.
            IOError: If there's an error reading the file.
            ValueError: If the file is empty.
            Exception: For any other unexpected errors.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"The file {file_path} does not exist.")
    
        if not os.access(file_path, os.R_OK):
            raise IOError(f"The file {file_path} is not readable.")
        bytes_array = []
        try:
            # Determine media type based on file extension
            _, extension = os.path.splitext(file_path)
            extension = extension.lower()
            media_type = {
                '.jpg': 'jpeg',
                '.jpeg': 'jpeg',
                '.png': 'png',
                '.gif': 'gif',
                '.webp': 'webp'
            }.get(extension, 'application/octet-stream')

            with open(file_path, "rb") as image_file:
                binary_data = image_file.read()
    
                if not binary_data:
                    raise ValueError(f"The file {file_path} is empty.")
                bytes_array.append(binary_data)
                return bytes_array, media_type
    
        except IOError as e:
            raise IOError(f"Error reading the file {file_path}: {str(e)}")
        except Exception as e:
            raise Exception(f"An unexpected error occurred: {str(e)}")

    '''
        def pdf_to_png_bytes(self, pdf_path, quality=75, max_size=(1024, 1024)):
            """
            Convert a PDF to a list of base64 encoded PNG images.
    
            Args:
                pdf_path (str): The path to the PDF file.
                quality (int): The quality of the PNG images (1-95). Defaults to 75.
                max_size (tuple): The maximum width and height of the images. Defaults to (1024, 1024).
    
            Returns:
                list: A list of base64 encoded PNG images, one for each page of the PDF.
            """
    
            if not os.path.exists(pdf_path):
                raise FileNotFoundError(f"The file {pdf_path} does not exist.")
        
            if not os.access(pdf_path, os.R_OK):
                raise IOError(f"The file {pdf_path} is not readable.")
            try:    
                doc = fitz.open(pdf_path)
                #base64_encoded_pngs = []
                image_pages = []
        
                for page_num in range(doc.page_count):
                    page = doc.load_page(page_num)
                    pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
                    image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
                    if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
                        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        
                    image_data = io.BytesIO()
                    image.save(image_data, format='PNG', optimize=True, quality=quality)
                    image_data.seek(0)
                    image_pages.append(image_data.getvalue())
        
            except fitz.FileDataError as e:
                raise ValueError(f"Error processing PDF: {str(e)}")
            except Exception as e:
                raise ValueError(f"Unexpected error processing PDF: {str(e)}")
            finally:
                doc.close()
            return image_pages


    '''
    