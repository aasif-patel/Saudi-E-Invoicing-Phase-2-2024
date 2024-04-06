import frappe
import os
import base64
import json

root_dir = os.getcwd() + frappe.get_site_path().removeprefix('.')

def set_content(from_csid=False):
    if from_csid:
        cert_file_path = root_dir+'/cert.pem'
        if cert_file_path:
            with open(cert_file_path, "r") as file:
                cert_content = file.read()
            if cert_content:
                frappe.db.set_single_value("CSR Config","certificate",cert_content)
    else:
        csr_file_path = get_latest_generated_csr_file()
        if csr_file_path:
            with open(csr_file_path, "r") as file:
                csr_content = file.read()
            if csr_content:
                frappe.db.set_single_value("CSR Config","csr",csr_content)

        private_key_file_path = root_dir+'/sdkprivatekey.pem'
        with open(private_key_file_path, "r") as file:
            pk_content = file.read()
        if pk_content:
            frappe.db.set_single_value("CSR Config","private_key",pk_content)

def get_latest_generated_csr_file(folder_path=frappe.get_site_path()):
    files = [folder_path+'/'+f for f in os.listdir(folder_path) if f.startswith("generated-csr") and os.path.isfile(os.path.join(folder_path, f))]
    if not files:
        raise Exception("CSR File not found.")
    latest_file = max(files, key=os.path.getmtime)

    return latest_file

def remove_header(text):
    header = "b'********** Welcome to ZATCA E-Invoice Java SDK 3.3.2 *********************\r\nThis SDK uses Java to call the SDK (jar) passing it an invoice XML file.\r\nIt can take a Standard or Simplified XML, Credit Note, or Debit Note.\r\nIt returns if the validation is successful or shows errors where the XML validation fails.\r\nIt checks for syntax and content as well.\r\nYou can use the command (fatoora -help) for more information.\r\n\r\n*****************************************************************************\n\nn"
    plan_msg = str(text)
    if plan_msg.startswith("b'**********"):
        msg_without_hdr = plan_msg[len(header):]
        if msg_without_hdr.endswith("\n'"):
            return msg_without_hdr.removesuffix("\n'")
        return msg_without_hdr
    return plan_msg

def xml_base64_Decode(signed_xmlfile_name):
    try:
        with open(signed_xmlfile_name, "r") as file:
            xml = file.read().lstrip()
            base64_encoded = base64.b64encode(xml.encode("utf-8"))
            base64_decoded = base64_encoded.decode("utf-8")
            return base64_decoded
    except Exception as e:
        raise Exception(e)

@frappe.whitelist()
def update_sdk_config(sdk_root):
    """
    Updating SDK config, removing default presit location with our ganerated cert and privatkey
    """
    try:
        path_to_change = {
            "certPath": root_dir+"/cert.pem",
            "privateKeyPath": root_dir+"/sdkprivatekey.pem",
            # "pihPath": root+"/Data/PIH/pih.txt"
        }
        try:
            with open(sdk_root+"/Configuration/config.json", "r") as file:
                sdk_config = json.load(file)
        except:
            frappe.throw("Can't able to read SDK config.")

        if sdk_config:
            custom_sdk_config = {}
            for key, value in sdk_config.items():
                if path_to_change.get(key):
                    custom_sdk_config[key]=path_to_change.get(key)
                else:
                    custom_sdk_config[key]=value

            if custom_sdk_config:
                try:
                    with open(frappe.get_module_path("zatca2024")+"/customizations/zatca/sdk_config.json", "w") as file:
                        json.dump(custom_sdk_config, file, indent=4)
                except:
                    frappe.throw("Can't able to update SDK Config.")

            frappe.msgprint("SDK Config Updated.", alert=1, indicator='green')

    except Exception as e:
        log = frappe.log_error(title='Error updating SDK Config',message=str(e))
        frappe.msgprint(f"Error updating SDK Config, <a href='/app/error-log/{log.name}' style='color: red;'>See Log</a>.", alert=1, indicator='red')
        

def update_files():
    """
    Check and upate the files, as server update might delete the created file
    [NOTE]:No need now, file stored in /sites/<site_name> are removed by server update
    """
    csr_doc = frappe.get_doc("CSR Config")
    # Checking csr config
    csr_config = root_dir+'/sdkcsrconfig.properties'

    if not os.path.exists(csr_config):
        if csr_doc.csr_config:
            with open(csr_config,"w") as file:
                file.write(csr_doc.csr_config)
        else:
            raise Exception("Please set the csr config first.")

    # Checking csr
    csr = root_dir+'/sdkcsr.pem'
    if not os.path.exists(csr):
        if csr_doc.csr:
            with open(csr,"w") as file:
                file.write(csr_doc.csr)
        else:
            raise Exception("CSR file not found or Not Created yet.")

    # Private key
    private_key = root_dir+'/sdkprivatekey.pem'
    if not os.path.exists(private_key):
        if csr_doc.private_key:
            with open(private_key,"w") as file:
                file.write(csr_doc.private_key)
        else:
            raise Exception("Private key not found.")
    
     # Certificate
    cert = os.getcwd()+'/cert.pem'
    if not os.path.exists(cert):
        if csr_doc.certificate:
            with open(cert,"w") as file:
                file.write(csr_doc.certificate)
        else:
            raise Exception("Certificate not found.")
        
