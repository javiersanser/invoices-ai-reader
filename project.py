# Invoices AI Reader
# entry point file

# Requirements
# We need to be able to open pdf files
# We need to be able to pass this files to a Gemini Model with multimodal capabilities
# We need to prompt the mode to extract a structured set of data
# We need to process the response of the model and made a JSON file wit it
import os
import sys
import json
from dotenv import load_dotenv
from google import genai
from google.genai.errors import ClientError


# Main
def main():
    try:
        load_dotenv()  # reads variables from a .env file and sets them in os.environ

        # Open the client. The client gets the API key from the environment variable `GEMINI_API_KEY`by docs of Google Gemini SDK without need to use os as referenced in the dotenv docs.
        client = genai.Client()
        option = 0
    except (EOFError,KeyboardInterrupt):
        client.close()
        print("\n Program terminated")

    while True:
        try:

            if option == 0:
                option = print_main_menu()
            elif option == 1:
                print_unprocessed_invoices()
                input("Press Enter to return to Main Menu")
                option = print_main_menu()
                continue
            elif option == 2:
                print_processed_json()
                input("Press Enter to return to Main Menu")
                option = print_main_menu()
                continue
            elif option == 3:
                try:
                    # Set default value for overwrite
                    overwrite = "N"
                    # Ask the user for the input file to extract data and create the name of the output file
                    invoice_file = input("Invoice file in pdf: ")
                    # This check could be made inside save_json_data, but doing it before saves API tokens as it doesn't call the model
                    if invoice_file not in get_invoices_pdf_list():
                        print("❌File not found")
                        option = print_main_menu()
                        continue

                    if invoice_file not in get_unprocessed_invoices():
                        overwrite = input("⚠️ This file has been already processed, do you want to overwrite it? (Y/N): ").upper()
                        if overwrite == "N":
                            option = print_main_menu()
                            continue #DEBUG , something weird happens here

                    json_file = invoice_file.removesuffix('.pdf')+'.json'
                    invoice_path = "invoices/"+invoice_file
                    json_path = "data/"+json_file
                    # Main operations with the client
                    # Parse data
                    d = gemini_parse_invoice(client, invoice_path)
                    # Save json with the data extracted
                    if overwrite == "Y":
                        save_json_data(d, json_path, write_mode ='w' )
                    else:
                        save_json_data(d, json_path, write_mode = 'x')
                    option = print_main_menu()
                except FileNotFoundError:
                    print("❌ Invoice file not found")
                    option = int(input("Type 3 to try again, 0 to return to menu: "))
                    if option == 0:
                        option = print_main_menu()

            elif option == 4:
                for invoice_file in get_unprocessed_invoices():
                    json_file = invoice_file.removesuffix('.pdf')+'.json'
                    invoice_path = "invoices/"+invoice_file
                    json_path = "data/"+json_file
                    # Main operations with the client
                    # Parse data
                    d = gemini_parse_invoice(client, invoice_path)
                    # Save json with the data extracted
                    save_json_data(d, json_path)
                option = print_main_menu()


            elif option == 5:
                    # Close client
                client.close()
                sys.exit("👋 The user exited the program")
            else:
                input("❌ The typed option doesn't exists, press Enter to return to menu")
                option = print_main_menu()

        except (EOFError, KeyboardInterrupt, UnboundLocalError):
            client.close()
            print("\n Program terminated")
            break


# Functions

# Gemini models

# This function is not currently used in project.py but it is used in test_project.py to assure the hardcoded model
# in gemini_parse_invoice function is supported. It could be used to refactor this last function or to build
# a prompt asking the user to provide a supported model and validate it.
def gemini_list_models(client):
    '''Get supported AI models from Gemini API'''
    models_list =[]
    for model in client.models.list():
        print(model.name)
        models_list.append(model.name)
    return models_list
        # print(f"Name: {model.name}")
        # print(f"Capacity: {model.supported_actions}")



def gemini_parse_invoice(client, invoice_file):
    ''' Returns a dictionary with the keys defined in get_invoice_schema and values extracted by the Gemini AI Model'''
    try:
        file = client.files.upload(file = invoice_file)
        response = client.models.generate_content(
        model='gemini-2.5-flash-lite', # lite is enough for this work, raises 404/ CLientError if not exists
        contents=[get_gemini_prompt(), file],
        config={
            'response_mime_type': 'application/json',
            'response_json_schema': get_invoice_json_schema()
        },
        )
        return response.parsed
    except ClientError:
        sys.exit("❌ Program terminated due to Gemini API error. Do you exceed your quota?")


# Define json schema with the structured data we want to extract from the pdf document
def get_invoice_json_schema():
    '''
    Returns a python dictionary with an structured json schema (https://json-schema.org/) with the required data fields to extract from an invoice document
    Data:
        - Invoice number
        - Date of issue
        - Issuer name
        - Client name
        - VAT Number
        - Taxable base ($)
        - Tax rate (%)
        - VAT Tax ($)
        - Invoice Total ($)
        - Currency
    '''
    invoice_schema ={"$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://example.com/product.schema.json",
        "title": "Invoice",
        "description": "An invoice document",
        "type": "object",
        "properties": {
            "invoiceId": {
            "description": "The number that identifies the invoice, usually a number but could be numbers and letters",
            "type": "string"
            },
            "invoiceDate": {
            "description": "The date that the invoice has been issued in ISO 8601 format",
            "type": "string"
            },
            "issuerName": {
            "description": "The name of the invoice issuer, usually a supplier or a vendor",
            "type": "string"
            },
            "clientName": {
            "description": "The name of the client to wich the invoice has been issued to",
            "type": "string"
            },
            "issuerTaxId": {
            "description": "The taxId of the issuer of the invoice, depending of country could be VAT number, Commerce registry number...",
            "type": "string"
            },
            "taxableBase": {
            "description": "The total amount of the invoice pre-tax in currency units, could be a subtotal to with taxes are added to conform the total amount ",
            "type": "number"
            },
            "taxRate": {
            "description": "The rate in percentage of the aplicable taxes, depending of country could be VAT rate or Sales tax.. ",
            "type": "number"
            },
            "taxAmount": {
            "description": "Amount of taxes derived from aplying the taxRate to the taxableBase in currency units",
            "type": "number"
            },
            "invoiceTotal": {
            "description": "The total and final amount of the invoice after taxes in currency units ",
            "type": "number"
            },
            "invoiceCurrency": {
            "description": "The currency in wich the amounts in the invoice document are denominated, depending of the country could be: USD, EUR, JPY, AUD, etc. ",
            "enum": ["USD", "EUR", "JPY", "AUD", "CAD", "NZD"],
            "type": "string"
            },
        },
         "required": [ "invoiceId", "invoiceDate", "issuerName", "issuerTaxId", "taxableBase", "invoiceTotal", "invoiceCurrency" ]
    }
    return invoice_schema

def save_json_data(d, json_file_name, write_mode = "x"):
    ''' Receives a dictionary as defined in get_invoice_json_schema and generated by gemini_parse_invoice and saves a file with the data for persistence'''
    try:
        with open(json_file_name, write_mode) as f: #if write_mode = 'w' the file will be overwrited and the error will not be raised
          json.dump(d,f)
        print(f"✅ File created: {json_file_name}")

    except FileExistsError:
        print("❌ The file name already exists")


def get_gemini_prompt():
    ''' returns the system prompt to be passed to the AI model'''

    prompt = """Act as an accounting expert, read the provided invoice file
    and extract the data as required by the json schema provided,
    in case some data required or optional is missing
    in the document, fill the corresponding json field as 'null' value,
    return always all the fields provided in the json schema in your response."""

    return prompt

# Get a list of files in input/output directories

def get_invoices_pdf_list():
    ''' Returns a python list object with the list of files in the invoices/ folder wich contains the files we want to extract data from.'''
    files = os.listdir("invoices")
    return files

def get_invoices_json_list():
    ''' Returns a python list object with the list of files in the data/ folder wich contains the files with extracted data in json format'''
    files = os.listdir("data")
    return files

def get_unprocessed_invoices():
    ''' Returns a list of files in invoices/ that doesn't have a parsed json in data/ folder.'''
    invoices_files = [invoice.removesuffix('.pdf') for invoice in get_invoices_pdf_list()]
    json_files = [json.removesuffix('.json') for json in get_invoices_json_list()]
    unprocessed_invoices = [i +'.pdf' for i in list(set(invoices_files)-set(json_files))]
    return unprocessed_invoices

def print_unprocessed_invoices():
    unprocessed_invoices = get_unprocessed_invoices()
    print("-"*50)
    print("LIST OF UNPROCESSED INVOICES")
    print("-"*50)
    for invoice in unprocessed_invoices:
        print(f"{unprocessed_invoices.index(invoice)+1} {invoice}")
    print("-"*50)

def print_processed_json():
    processed_json = get_invoices_json_list()
    print("-"*50)
    print("LIST OF PROCESSED JSON")
    print("-"*50)
    for json in processed_json:
        print(f"{processed_json.index(json)+1} {json}")
    print("-"*50)

def print_main_menu():
    print("-"*60)
    print("INVOICES AI READER - MAIN MENU")
    print("-"*60)
    print("1 - Show a list of unprocessed invoices files")
    print("2 - Show a list of processed json files")
    print("3 - Type the file name to process")
    print("4 - Process in bulk the unprocessed invoices")
    print("5 - Exit the program (you could also press Ctrl + C)")
    print("-"*60)
    option = int(input("Type the desired option (1,2,3,4,5) and press Enter: "))
    return option

# End of file
if __name__ == "__main__":
    main()

