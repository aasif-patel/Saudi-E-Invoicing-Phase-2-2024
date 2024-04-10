import frappe
import os
import re
import xml.etree.ElementTree as ET
from frappe import _
from frappe.utils import nowdate
from zatca2024.zatca2024.customizations.zatca.createxml import xml_tags,salesinvoice_data,invoice_Typecode_Simplified,invoice_Typecode_Standard,doc_Reference,additional_Reference ,company_Data,customer_Data,delivery_And_PaymentMeans,tax_Data,item_data,invoice_Typecode_Compliance,delivery_And_PaymentMeans_for_Compliance,doc_Reference_compliance,get_tax_total_from_items
from zatca2024.zatca2024.customizations.zatca.compliance import get_pwd,set_cert_path,create_compliance_x509,check_compliance
from zatca2024.zatca2024.customizations.zatca.create_xml import create_plain_invoice, xml_structuring
from zatca2024.zatca2024.customizations.zatca.file_manager import set_content, get_latest_generated_csr_file
from zatca2024.zatca2024.customizations.zatca.zatca_api_call import compliance_api_call, reporting_API, clearance_API


root_dir = frappe.get_site_path()
sdk_config = frappe.get_module_path("zatca2024")+"/customizations/zatca/sdk_config.json"

def _execute_in_shell(cmd, verbose=False, low_priority=False, check_exit_code=False):
    # using Popen instead of os.system - as recommended by python docs
    import shlex
    import tempfile
    from subprocess import Popen
    env_variables = {"MY_VARIABLE": "some_value", "ANOTHER_VARIABLE": "another_value"}
    if isinstance(cmd, list):
        # ensure it's properly escaped; only a single string argument executes via shell
        cmd = shlex.join(cmd)

    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        kwargs = {"shell": True, "stdout": stdout, "stderr": stderr, "cwd":root_dir}
        if low_priority:
            kwargs["preexec_fn"] = lambda: os.nice(10)
        p = Popen(cmd, **kwargs)
        exit_code = p.wait()
        stdout.seek(0)
        out = stdout.read()
        stderr.seek(0)
        err = stderr.read()
    failed = check_exit_code and exit_code

    if verbose or failed:
        if err:
            frappe.msgprint(err)
        if out:
            frappe.msgprint(out)
    if failed:
        raise Exception("Command failed")
    return err, out


@frappe.whitelist(allow_guest=True)
def generate_csr():
    try:
        csr_file_path = root_dir+'/sdkcsrconfig.properties'
        if not os.path.exists(csr_file_path): raise Exception("Please set the csr config first.")

        settings=frappe.get_doc('Zatca setting')
        csr_config_file = 'sdkcsrconfig.properties'
        private_key_file = 'sdkprivatekey.pem'
        generated_csr_file = 'sdkcsr.pem'
        SDK_ROOT=settings.sdk_root
        path_string=f"export SDK_ROOT={SDK_ROOT} && export FATOORA_HOME=$SDK_ROOT/Apps && export SDK_CONFIG={sdk_config} && export PATH=$PATH:$FATOORA_HOME &&  "
        
        if settings.select in ["Simulation", "Sandbox"]:
            command_generate_csr =  path_string  + f'fatoora -sim -csr -csrConfig {csr_config_file} -privateKey {private_key_file} -generatedCsr {generated_csr_file} -pem'
        else:
            command_generate_csr =  path_string  + f'fatoora -csr -csrConfig {csr_config_file} -privateKey {private_key_file} -generatedCsr {generated_csr_file} -pem'
        
        try:
            err,out = _execute_in_shell(command_generate_csr)

            with open(get_latest_generated_csr_file(), "r") as file_csr:
                get_csr = file_csr.read()

            file = frappe.get_doc({
                    "doctype": "File",
                    "file_name": f"generated-csr-{nowdate()}.csr",
                    "attached_to_doctype": settings.doctype,
                    "attached_to_name": settings.name,
                    "content": get_csr 
                    })
            file.save(ignore_permissions=True)
            set_content()
            frappe.msgprint(out)

        except Exception as e:
            raise Exception(e)

    except Exception as e:
        log = log_error(title="Error Generating CSR", alert=False)
        frappe.throw(f"Error Generating CSR, See <a href='/app/error-log/{log}' style='color:red'>Error Log</a>")


def sign_invoice():
    settings=frappe.get_doc('Zatca setting')
    xmlfile_name = os.getcwd()+'/invoice.xml'
    signed_xmlfile_name = os.getcwd()+'/sign_invoice.xml'
    SDK_ROOT= settings.sdk_root
    path_string=f"export SDK_ROOT={SDK_ROOT} && export FATOORA_HOME=$SDK_ROOT/Apps && export SDK_CONFIG={sdk_config} && export PATH=$PATH:$FATOORA_HOME &&  "
    
    command_sign_invoice = path_string  + f'fatoora -sign -invoice {xmlfile_name} -signedInvoice {signed_xmlfile_name}'

    err,out = _execute_in_shell(command_sign_invoice)
    
    match = re.search(r'ERROR', err.decode("utf-8"))
    if match:
        raise Exception(err)

    match = re.search(r'ERROR', out.decode("utf-8"))
    if match:
        raise Exception(out)
    
    match = re.search(r'INVOICE HASH = (.+)', out.decode("utf-8"))
    if match:
        invoice_hash = match.group(1)
        return signed_xmlfile_name , path_string
    else:
        raise Exception(err,out)

            
def generate_qr_code(signed_xmlfile_name,sales_invoice_doc,path_string):
    command_generate_qr =path_string  + f'fatoora -qr -invoice {signed_xmlfile_name}'
    err,out = _execute_in_shell(command_generate_qr)
    qr_code_match = re.search(r'QR code = (.+)', out.decode("utf-8"))
    if qr_code_match:
        qr_code_value = qr_code_match.group(1)
        return qr_code_value
    else:
        raise Exception("QR Code not found in the output.")
   
           
def generate_hash(signed_xmlfile_name,path_string):
    command_generate_hash = path_string  + f'fatoora -generateHash -invoice {signed_xmlfile_name}'
    err,out = _execute_in_shell(command_generate_hash)
    invoice_hash_match = re.search(r'INVOICE HASH = (.+)', out.decode("utf-8"))
    if invoice_hash_match:
        hash_value = invoice_hash_match.group(1)
        # frappe.msgprint("The hash value: " + hash_value)
        return hash_value
    else:
        raise Exception("Hash value not found in the log entry.")


def validate_invoice(signed_xmlfile_name,path_string):               
    try:
        command_validate_hash = path_string  + f'fatoora -validate -invoice {signed_xmlfile_name}'
        err,out = _execute_in_shell(command_validate_hash)
        pattern_global_result = re.search(r'\*\*\* GLOBAL VALIDATION RESULT = (\w+)', out.decode("utf-8"))
        global_result = pattern_global_result.group(1) if pattern_global_result else None
        global_validation_result = 'PASSED' if global_result == 'PASSED' else 'FAILED'
        if global_validation_result == 'FAILED':
            frappe.msgprint(out)
            frappe.msgprint(err)
            frappe.msgprint(_("Validation has been failed"))
        else:
            frappe.msgprint(out)
            frappe.msgprint(err)
            frappe.msgprint(_("Validation has been done Successfully"))
    except Exception as e:
            frappe.throw(_("Error Validating Invoice: {0}").format(str(e)))  


def error_Log():
    try:
        frappe.log_error(title='Zatca invoice call failed in clearance status',message=frappe.get_traceback())
    except Exception as e:
        frappe.throw(_("Error in error log")+" "+ str(e))


@frappe.whitelist(allow_guest=True) 
def zatca_Call(invoice_doc, compliance_type="0"):
    try:
        is_b2c_customer = frappe.db.get_value("Customer",invoice_doc.customer,"custom_b2c")
        if compliance_type == "0":
            if is_b2c_customer == 1:
                inv_type = "B2C" #invoice_Typecode_Simplified(invoice, sales_invoice_doc)
            else:
                inv_type = "B2B" #invoice_Typecode_Standard(invoice, sales_invoice_doc)
        else:
            if compliance_type in ['1','3','5']: # Simplied
                inv_type = "B2C" # invoice_Typecode_Compliance(invoice, compliance_type)
            else: # Standar
                inv_type = "B2B"

        invoice,uuid_str = create_plain_invoice(invoice_doc,inv_type,compliance_type)
        xml_structuring(invoice,invoice_doc)
        signed_xmlfile_name,path_string=sign_invoice()
        qr_code_value = generate_qr_code(signed_xmlfile_name,invoice_doc,path_string)
        hash_value = generate_hash(signed_xmlfile_name,path_string)

    except Exception as e:
        log = log_error(title="Error Ganerating or Siging XML", alert=False)
        frappe.throw(f"Error Ganerating or Siging XML, See <a href='/app/error-log/{log}' style='color:red'>Error Log</a>")
    
    try:
        if compliance_type == "0":
            if is_b2c_customer == 1:
                reporting_API(uuid_str, hash_value, signed_xmlfile_name, invoice_doc, qr_code_value)
            else:
                clearance_API(uuid_str, hash_value, signed_xmlfile_name,invoice_doc.name,invoice_doc)

        else:  # if it a compliance test
            compliance_api_call(uuid_str, hash_value, signed_xmlfile_name)

    except:
        log = log_error(title="Error Calling Zatca API", alert=False)
        frappe.throw(f"Error Calling Zatca API, See <a href='/app/error-log/{log}' style='color:red'>Error Log</a>")


@frappe.whitelist(allow_guest=True) 
def zatca_Call_compliance(invoice_number, compliance_type="0"):
    """
        0 is default. Actual Reporting.
        1 is for compliance test. Simplified invoice
        2 is for compliance test. Standard invoice
        3 is for compliance test. Simplified Credit Note
        4 is for compliance test. Standard Credit Note
        5 is for compliance test. Simplified Debit Note
        6 is for compliance test. Standard Debit Note
    """
    try:
        settings = frappe.get_doc('Zatca setting')
        if settings.validation_type == "Simplified Invoice":
            compliance_type="1"
            inv_type = "B2C"
        elif settings.validation_type == "Standard Invoice":
            compliance_type="2"
            inv_type = "B2B"
        elif settings.validation_type == "Simplified Credit Note":
            compliance_type="3"
            inv_type = "B2C"
        elif settings.validation_type == "Standard Credit Note":
            compliance_type="4"
            inv_type = "B2B"
        elif settings.validation_type == "Simplified Debit Note":
            compliance_type="5"
            inv_type = "B2C"
        elif settings.validation_type == "Standard Debit Note":
            compliance_type="6"
            inv_type = "B2B"
                    
        if not frappe.db.exists("Sales Invoice", invoice_number):
            frappe.throw(_("Invoice Number is NOT Valid : {0}").format(str(invoice_number)))
        
        sales_invoice_doc = frappe.get_doc("Sales Invoice",invoice_number)
        invoice, uuid1 = create_plain_invoice(sales_invoice_doc,inv_type,compliance_type)
        xml_structuring(invoice,sales_invoice_doc)
        signed_xmlfile_name,path_string = sign_invoice()
        generate_qr_code(signed_xmlfile_name,sales_invoice_doc,path_string)
        hash_value = generate_hash(signed_xmlfile_name,path_string)

    except Exception as e:
        log = log_error(title="Error Ganerating or Signing XML", alert=False)
        frappe.throw(_("Error Ganerating or Signing XML, See <a href='/app/error-log/{0}' style='color:red'>Error Log</a>").format(log))

    try:
        compliance_api_call(uuid1, hash_value, signed_xmlfile_name)

    except Exception as e:
        log = log_error(title="Error In Compliance API Call", alert=False)
        frappe.throw(_("Error In Compliance API CallL, See <a href='/app/error-log/{0}' style='color:red'>Error Log</a>").format(log))
    

@frappe.whitelist()          
def zatca_Background_on_submit(invoice_number=None,invoice_doc=None):              
    settings = frappe.get_doc('Zatca setting')
    if settings.zatca_invoice_enabled == 1:
        if invoice_doc:
            sales_invoice_doc = invoice_doc
        if invoice_number:
            sales_invoice_doc= frappe.get_doc("Sales Invoice",invoice_number )
            if sales_invoice_doc.docstatus == 0:
                frappe.throw(_("Please submit the invoice before sending to Zatca : {0}").format(sales_invoice_doc.name))
            if sales_invoice_doc.docstatus == 2:
                frappe.throw(_("Can not send Cancelled invoice to Zatca : {0}").format(sales_invoice_doc.name))

        if not frappe.db.exists("Sales Invoice", sales_invoice_doc.name):
            frappe.throw(_("Invoice:{0} does not exist.").format(sales_invoice_doc.name))
            
        if sales_invoice_doc.custom_zatca_status == "REPORTED" or sales_invoice_doc.custom_zatca_status == "CLEARED":
            frappe.throw(_("Already submitted to ZATCA."))
        
        zatca_Call(sales_invoice_doc,"0")
    else:
        frappe.smgprint(_("Zatca is not enabled."))


def log_error(title="Error",alert=True):
        log = frappe.log_error(title=title,message=frappe.get_traceback())
        if alert:
            frappe.msgprint(f"An Error Occures, see <a href='/app/error-log/{log.name}' style='color: red;'>Error Log</a> for more detail.", alert=1, indicator='red')
        else:
            return log.name


# @frappe.whitelist(allow_guest=True)                  
# def zatca_Background(invoice_number):
#     try:
#         settings = frappe.get_doc('Zatca setting')
        
#         if settings.zatca_invoice_enabled != 1:
#             frappe.throw(_("Zatca Invoice is not enabled in Zatca Settings."))
                                        
#         sales_invoice_doc= frappe.get_doc("Sales Invoice",invoice_number )

#         if sales_invoice_doc.docstatus in [0,2]:
#             frappe.throw(_("Please submit the invoice before sending to Zatca"))
            
#         if sales_invoice_doc.custom_zatca_status == "REPORTED" or sales_invoice_doc.custom_zatca_status == "CLEARED":
#             frappe.throw(_("Invoice already submitted to Zatca."))
        
#         zatca_Call(sales_invoice_doc,0)
        
#     except Exception as e:
#         frappe.throw("Error in background call:  " + str(e) )


        # create_compliance_x509()
        # frappe.throw("Created compliance x509 certificate")
        # if not frappe.db.exists("Sales Invoice", invoice_number):
        #     frappe.throw(_("Invoice Number is NOT Valid:  " + str(invoice_number)))
        # invoice= xml_tags()
        # invoice,uuid1,sales_invoice_doc=salesinvoice_data(invoice,invoice_number)
        # invoice=doc_Reference(invoice,invoice_doc,invoice_doc.name)
        # invoice=additional_Reference(invoice)
        # invoice=company_Data(invoice,invoice_doc)
        # invoice=customer_Data(invoice,invoice_doc)
        # invoice=delivery_And_PaymentMeans(invoice,invoice_doc, invoice_doc.is_return) 
        # invoice=tax_Data(invoice,invoice_doc)
        # invoice=item_data(invoice,invoice_doc)
        # validate_invoice(signed_xmlfile_name,path_string)
        # frappe.msgprint("validated and stopped it here")
        # result,clearance_status=send_invoice_for_clearance_normal(uuid1,signed_xmlfile_name,hash_value)



        # invoice,sales_invoice_doc, uuid1 = create_plain_invoice(invoice_number) #xml_tags()
        # invoice,uuid1,sales_invoice_doc=salesinvoice_data(invoice_number)
        # customer_doc= frappe.get_doc("Customer",sales_invoice_doc.customer)
        
        # invoice = invoice_Typecode_Compliance(invoice, compliance_type)
        
        # invoice=doc_Reference_compliance(invoice,sales_invoice_doc,invoice_number,compliance_type)
        # invoice=additional_Reference(invoice)
        # invoice=company_Data(invoice,sales_invoice_doc)
        # invoice=customer_Data(invoice,sales_invoice_doc)
        # invoice=delivery_And_PaymentMeans_for_Compliance(invoice,sales_invoice_doc,compliance_type) 
        # invoice=tax_Data(invoice,sales_invoice_doc)
        # invoice=item_data(invoice,sales_invoice_doc)

        # validate_invoice(signed_xmlfile_name,path_string)
        # frappe.msgprint("validated and stopped it here")
        # result,clearance_status=send_invoice_for_clearance_normal(uuid1,signed_xmlfile_name,hash_value)

        # frappe.msgprint("Compliance test")
    # except ErrorInCompliance as e:
    #         frappe.throw("<b>Error:</b> "+str(e))

# import xml.etree.ElementTree as ElementTree
# from frappe.utils import execute_in_shell
# import xml.dom.minidom as minidom
# from frappe.utils.data import get_time
# from frappe.utils import now
# import xml.etree.ElementTree as ET
# from datetime import datetime
# frappe.init(site="prod.erpgulf.com")
# frappe.connect()
# from lxml import etree
# import sys

# def clean_up_certificate_string(certificate_string):
#     return certificate_string.replace("-----BEGIN CERTIFICATE-----\n", "").replace("-----END CERTIFICATE-----", "").strip()

# def get_auth_headers(certificate=None, secret=None):
#     if certificate and secret:
#         certificate_stripped = clean_up_certificate_string(certificate)
#         certificate_base64 = base64.b64encode(certificate_stripped.encode()).decode()
#         credentials = f"{certificate_base64}:{secret}"
#         basic_token = base64.b64encode(credentials.encode()).decode()
#         return basic_token       
#     return {}
         
# #                     # frappe.enqueue(
#                     #         zatca_Call,
#                     #         queue="short",
#                     #         timeout=200,
#                     #         invoice_number=invoice_number)
#                     # frappe.msgprint("queued")
# #                     # frappe.enqueue(
#                     #         zatca_Call,
#                     #         queue="short",
#                     #         timeout=200,
#                     #         invoice_number=invoice_number)
#                     # frappe.msgprint("queued")
