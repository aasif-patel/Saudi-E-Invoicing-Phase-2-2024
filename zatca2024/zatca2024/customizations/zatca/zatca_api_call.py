import frappe
from frappe import _
import json
import requests
import base64
from zatca2024.zatca2024.customizations.zatca.file_manager import (
    xml_base64_Decode,
    get_latest_generated_csr_file,
    set_content,
    attach_QR_Image_For_Reporting,
    attach_sign_xml,
    attach_QR_Image_For_Clearance
    )

root_dir = frappe.get_site_path()

def get_API_url(base_url):
    
    settings = frappe.get_doc('Zatca setting')
    if settings.select == "Sandbox":
        url = settings.sandbox_url + base_url
    elif settings.select == "Simulation":
        url = settings.simulation_url + base_url
    else:
        url = settings.production_url + base_url
    
    if not url:
        raise Exception("URL not found in Zatca setting.")

    return url

def compliance_api_call(uuid1,hash_value, signed_xmlfile_name ):
    message_dic = {"200":"HTTP OK","400":"HTTP Bad Request. Invalid Request.","401":"Unauthorized. Username or Password is incorrect","500":"HTTP Internal Server Error."}

    settings = frappe.get_doc('Zatca setting')
    payload = json.dumps({
        "invoiceHash": hash_value,
        "uuid": uuid1,
        "invoice": xml_base64_Decode(signed_xmlfile_name) })

    headers = {
        'accept': 'application/json',
        'Accept-Language': 'en',
        'Accept-Version': 'V2',
        'Authorization': "Basic " + settings.basic_auth,
        'Content-Type': 'application/json'  }

    response = requests.request("POST", url=get_API_url(base_url="compliance/invoices"), headers=headers, data=payload)
    sts_code = response.status_code
    try:
        if isinstance(response.text, str):
            response_msg = json.loads(response.text)
    except:
        response_msg = response.text

    if sts_code == 200:        
        msg = response_msg.get("reportingStatus") if response_msg.get("reportingStatus") else response_msg.get("clearanceStatus")
        zatca_api_log(json.dumps(response_msg), sts_code, title="Zatca Complaince Call.",uuid=uuid1, status_msg=message_dic)
        frappe.msgprint(f"<b style='color:green;'>Compliance Successfull :</b> {msg}</b>")

    else:
        zatca_api_log(response_msg, sts_code, title="Zatca Complaince Call.", uuid=uuid1, status_msg= message_dic,alert=True)

    
@frappe.whitelist(allow_guest=True)
def create_CSID(): 
    try:
        message_dic = {"200":"HTTP OK","400":"HTTP Bad Request. Invalid Request.","406":"This Version is not supported or not provided in the header.","500":"HTTP Internal Server Error."}
        settings=frappe.get_doc('Zatca setting')
        with open(get_latest_generated_csr_file(), "r") as f:
            csr_contents = f.read()

        payload = json.dumps({
        "csr": csr_contents
        })

        headers = {
        'accept': 'application/json',
        'OTP': settings.otp,
        'Accept-Version': 'V2',
        'Content-Type': 'application/json'
        }

        response = requests.request("POST", url=get_API_url(base_url="compliance"), headers=headers, data=payload)

        sts_code = response.status_code
        try:
            if isinstance(response.text, str):
                response_msg = json.loads(response.text)
        except:
            response_msg = response.text

        if response.status_code == 200:
            concatenated_value = f'{response_msg["binarySecurityToken"]}:{response_msg["secret"]}'
            encoded_value = base64.b64encode(concatenated_value.encode()).decode()

            with open(root_dir+"/cert.pem", 'w') as file:   #attaching X509 certificate
                file.write(base64.b64decode(response_msg["binarySecurityToken"]).decode('utf-8'))

            set_content(from_csid=True)
            settings.set("basic_auth", encoded_value)
            settings.set("compliance_request_id",response_msg["requestID"])
            settings.save(ignore_permissions=True)

            msg = response_msg.get("dispositionMessage")
            zatca_api_log(response_msg, sts_code, title="CSID Creation", status_msg=message_dic)
            frappe.msgprint(f"<b style='color:green;'>CSID Created :</b> {msg}")
    
        elif response.status_code == 400:
            log = zatca_api_log(response_msg, sts_code, title="CSID Creation", status_msg=message_dic)
            frappe.msgprint(f"<b style='color: red;'>Error :</b> OTP is not valid, see the <a href='/app/zatca-success-log/{log}' style='color: red;'>See Log</a>")

        else:
            zatca_api_log(response_msg, sts_code, title="CSID Creation", status_msg=message_dic, alert=True)
        
    except Exception as e:
        #Error Log
        frappe.throw(_("Error in csid formation :{0}").format(str(e)))

@frappe.whitelist(allow_guest=True)                   
def production_CSID():    
    try:
        message_dic = {"200":"HTTP OK","400":"HTTP Bad Request. Invalid Request.","406":"This Version is not supported or not provided in the header.","500":"HTTP Internal Server Error."}
        settings = frappe.get_doc('Zatca setting')
        payload = json.dumps({
        "compliance_request_id": settings.compliance_request_id })
        
        headers = {
        'accept': 'application/json',
        'Accept-Version': 'V2',
        'Authorization': 'Basic'+ settings.basic_auth,
        'Content-Type': 'application/json' }

        response = requests.request("POST", url=get_API_url(base_url="production/csids"), headers=headers, data=payload)
        
        sts_code = response.status_code
        try:
            if isinstance(response.text, str):
                response_msg = json.loads(response.text)
        except:
            response_msg = response.text

        if sts_code == 200:
            concatenated_value = response_msg["binarySecurityToken"] + ":" + response_msg["secret"]
            encoded_value = base64.b64encode(concatenated_value.encode()).decode()
            
            with open(f"cert.pem", 'w') as file:   #attaching X509 certificate
                file.write(base64.b64decode(response_msg["binarySecurityToken"]).decode('utf-8'))
            
            settings.set("basic_auth_production", encoded_value)
            settings.save(ignore_permissions=True)

            msg = response_msg.get("dispositionMessage")
            zatca_api_log(response_msg, sts_code, title="Production CSID Creation", status_msg=message_dic)
            frappe.msgprint(f"<b style='color:green;'>Production CSID Created :</b> {msg}")
        else:
            zatca_api_log(response_msg, sts_code, title="Production CSID Creation", status_msg=message_dic, alert=True)

    except Exception as e:
        #Error Log
        frappe.throw(_("Error in Prodction CSID formation : {0}").format(str(e)))


def reporting_API(uuid1, hash_value, signed_xmlfile_name, sales_invoice_doc, qr_code_value):
    message_dic = {"200":"HTTP OK","400":"HTTP Bad Request. Invalid Request.","401":"Unauthorized","406":"This Version is not supported or not provided in the header.","500":"HTTP Internal Server Error."}
    settings = frappe.get_doc('Zatca setting')
    
    if settings.select in ['Simulation', 'Sandbox']:
        if not settings.basic_auth:
            raise Exception("Compliance CSID is not ganerated.")

        authorization = 'Basic ' + settings.basic_auth
    else:
        if not settings.basic_auth_production:
            raise Exception("Production CSID is not ganerated.")

        authorization = 'Basic ' + settings.basic_auth_production

    payload = json.dumps({
    "invoiceHash": hash_value,
    "uuid": uuid1,
    "invoice": xml_base64_Decode(signed_xmlfile_name),
    })

    headers = {
    'accept': 'application/json',
    'accept-language': 'en',
    'Clearance-Status': '0',
    'Accept-Version': 'V2',
    'Authorization': authorization, #'Basic' + settings.basic_auth_production,
    'Content-Type': 'application/json',
    # 'Cookie': 'TS0106293e=0132a679c0639d13d069bcba831384623a2ca6da47fac8d91bef610c47c7119dcdd3b817f963ec301682dae864351c67ee3a402866'
    }

    response = requests.request("POST", url=get_API_url(base_url="invoices/reporting/single"), headers=headers, data=payload)

    sts_code = response.status_code
    try:
        if isinstance(response.text, str):
            response_msg = json.loads(response.text)
    except:
        response_msg = response.text
        
    if sts_code  in [200, 202]:
        if sts_code == 202:
            log = zatca_api_log(response_msg, sts_code, title="Reporting Invoice", uuid=uuid1,invoice_number=sales_invoice_doc.name, status_msg=message_dic)
            msg = f"<b style:'color':'orange'>{response_msg.get('status')} WITH WARNIGS </b>: Fix the warnings before next submission, <a href='/app/zatca-success-log/{log}' style='color: red;'>See Log</a>"
            frappe.msgprint(msg)
        else:
            msg = f"<b style:'color':'green'>{response_msg.get('status')}"
            zatca_api_log(response_msg, sts_code, title="Reporting Invoice", uuid=uuid1,invoice_number=sales_invoice_doc.name, status_msg=message_dic)
            frappe.msgprint(msg)
        
        settings.pih = hash_value
        settings.save(ignore_permissions=True)

        sales_invoice_doc.db_set('custom_uuid' , uuid1 , commit=True  , update_modified=True)
        sales_invoice_doc.db_set('custom_zatca_status' , 'REPORTED' , commit=True  , update_modified=True)

        if settings.attach_sign_xml:
            attach_sign_xml(signed_xmlfile_name, sales_invoice_doc)

        if settings.attach_qr_code:
            attach_QR_Image_For_Reporting(qr_code_value, sales_invoice_doc)

    else:
        zatca_api_log(response_msg, sts_code, title="Reporting Invoice", uuid=uuid1, invoice_number=sales_invoice_doc.name, status_msg=message_dic, alert=True)

    # if response.status_code  in (400,405,406,409 ):
    #     invoice_doc = frappe.get_doc('Sales Invoice' , invoice_number )
    #     invoice_doc.db_set('custom_uuid' , 'Not Submitted' , commit=True  , update_modified=True)
    #     invoice_doc.db_set('custom_zatca_status' , 'Not Submitted' , commit=True  , update_modified=True)

    #     frappe.throw("Error: The request you are sending to Zatca is in incorrect format. Please report to system administrator . Status code:  " + str(response.status_code) + "<br><br> " + response.text )            
    
    # if response.status_code  in (401,403,407,451 ):
    #     invoice_doc = frappe.get_doc('Sales Invoice' , invoice_number  )
    #     invoice_doc.db_set('custom_uuid' , 'Not Submitted' , commit=True  , update_modified=True)
    #     invoice_doc.db_set('custom_zatca_status' , 'Not Submitted' , commit=True  , update_modified=True)

    #     frappe.throw("Error: Zatca Authentication failed. Your access token may be expired or not valid. Please contact your system administrator. Status code:  " + str(response.status_code) + "<br><br> " + response.text)            
    
    # if response.status_code not in (200, 202):
    #     invoice_doc = frappe.get_doc('Sales Invoice' , invoice_number  )
    #     invoice_doc.db_set('custom_uuid' , 'Not Submitted' , commit=True  , update_modified=True)
    #     invoice_doc.db_set('custom_zatca_status' , 'Not Submitted' , commit=True  , update_modified=True)
        
    #     frappe.throw("Error: Zatca server busy or not responding. Try after sometime or contact your system administrator. Status code:  " + str(response.status_code)+ "<br><br> " + response.text )


def clearance_API(uuid1,hash_value,signed_xmlfile_name,invoice_number,sales_invoice_doc):
    message_dic = {"200":"HTTP OK","400":"HTTP Bad Request. Invalid Request.","406":"This Version is not supported or not provided in the header.","500":"HTTP Internal Server Error."}
    settings = frappe.get_doc('Zatca setting')

    if settings.select in ['Simulation', 'Sandbox']:
        if not settings.basic_auth:
            raise Exception("Compliance CSID is not ganerated.")

        authorization = 'Basic ' + settings.basic_auth
    else:
        if not settings.basic_auth_production:
            raise Exception("Production CSID is not ganerated.")

        authorization = 'Basic ' + settings.basic_auth_production

    payload = json.dumps({
        "invoiceHash": hash_value,
        "uuid": uuid1,
        "invoice": xml_base64_Decode(signed_xmlfile_name)
    })

    headers = {
        'Accept': 'application/json',
        'Accept-Language': 'en',
        'Clearance-Status': '1',
        'Accept-Version': 'V2',
        'Authorization': authorization, #'Basic' + settings.basic_auth_production,
        'Content-Type': 'application/json'
    }
    
    response = requests.request("POST", url=get_API_url(base_url="invoices/clearance/single"), headers=headers, data=payload)
    
    sts_code = response.status_code

    try:
        if isinstance(response.text, str):
            response_msg = json.loads(response.text)
    except:
        response_msg = response.text
        
    if sts_code  in [200, 202]:
        if sts_code == 202:
            log = zatca_api_log(response_msg, sts_code, title="Invoice Clearance", uuid=uuid1,invoice_number=invoice_number, status_msg=message_dic)
            msg = f"<b style:'color':'orange'>{response_msg.get('status')} WITH WARNIGS </b>: Fix the warnings before next submission, <a href='/app/zatca-success-log/{log}' style='color: red;'>See Log</a>"
            frappe.msgprint(msg)
        else:
            msg = f"<b style:'color':'green'>{response_msg.get('status')}"
            zatca_api_log(response_msg, sts_code, title="Invoice Clearance", uuid=uuid1,invoice_number=invoice_number, status_msg=message_dic)
            frappe.msgprint(msg)
        
        settings.pih = hash_value
        settings.save(ignore_permissions=True)
        
        invoice_doc = frappe.get_doc('Sales Invoice' , invoice_number )
        invoice_doc.db_set('custom_uuid' , uuid1 , commit=True  , update_modified=True)
        invoice_doc.db_set('custom_zatca_status' , 'CLEARED' , commit=True  , update_modified=True)

        if settings.attach_sign_xml:
            base64_xml = response_msg["clearedInvoice"]
            xml_cleared= base64.b64decode(base64_xml).decode('utf-8')

            #attaching the cleared xml
            file = frappe.get_doc({
                "doctype": "File",
                "file_name": "E-Sign-invoice-" + sales_invoice_doc.name,
                "attached_to_doctype": sales_invoice_doc.doctype,
                "attached_to_name": sales_invoice_doc.name,
                "content": xml_cleared
            })
            file.save(ignore_permissions=True)
        
        if settings.attach_qr_code:
            attach_QR_Image_For_Clearance(xml_cleared, invoice_doc)

        return xml_cleared

    else:
        zatca_api_log(response_msg, sts_code, title="Invoice Clearance", uuid=uuid1, invoice_number=invoice_number, status_msg=message_dic, alert=True)

    # if response.status_code  in (400,405,406,409 ):
    #     invoice_doc = frappe.get_doc('Sales Invoice' , invoice_number  )
    #     invoice_doc.db_set('custom_uuid' , "Not Submitted" , commit=True  , update_modified=True)
    #     invoice_doc.db_set('custom_zatca_status' , "Not Submitted" , commit=True  , update_modified=True)
    #     frappe.throw("Error: The request you are sending to Zatca is in incorrect format. Please report to system administrator . Status code:  " + str(response.status_code) + "<br><br> " + response.text )            
    
    # if response.status_code  in (401,403,407,451 ):
    #     invoice_doc = frappe.get_doc('Sales Invoice' , invoice_number  )
    #     invoice_doc.db_set('custom_uuid' , "Not Submitted" , commit=True  , update_modified=True)
    #     invoice_doc.db_set('custom_zatca_status' , "Not Submitted" , commit=True  , update_modified=True)
    #     frappe.throw("Error: Zatca Authentication failed. Your access token may be expired or not valid. Please contact your system administrator. Status code:  " + str(response.status_code) + "<br><br> " + response.text)            
    
    # if response.status_code not in (200, 202):
    #     invoice_doc = frappe.get_doc('Sales Invoice' , invoice_number  )
    #     invoice_doc.db_set('custom_uuid' , "Not Submitted" , commit=True  , update_modified=True)
    #     invoice_doc.db_set('custom_zatca_status' , "Not Submitted" , commit=True  , update_modified=True)
    #     frappe.throw("Error: Zatca server busy or not responding. Try after sometime or contact your system administrator. Status code:  " + str(response.status_code))
    
    # if response.status_code  in (200, 202):
    #     if response.status_code == 202:
    #         msg = "CLEARED WITH WARNIGS: <br> <br> Please copy the below message and send it to your system administrator to fix this warnings before next submission <br>  <br><br> "
        
    #     if response.status_code == 200:
    #         msg = "SUCCESS: <br>   <br><br> "
        
        # settings.pih = hash_value
        # settings.save(ignore_permissions=True)
        
        # invoice_doc = frappe.get_doc('Sales Invoice' , invoice_number )
        # invoice_doc.db_set('custom_uuid' , uuid1 , commit=True  , update_modified=True)
        # invoice_doc.db_set('custom_zatca_status' , "CLEARED" , commit=True  , update_modified=True)


def zatca_api_log(response_text, status_code, title=None, uuid=None, invoice_number=None, status_msg={}, alert=False):
    
    if isinstance(response_text, dict):
            zatca_msg = json.dumps(response_text, indent=4)
    else:
        zatca_msg = response_text

    log =frappe.get_doc({
        "doctype": "Zatca Success log",
        "title": "Zatca api log." if not title else title,
        "status": status_code,
        "zatca_response": zatca_msg,
        "invoice_number": invoice_number,
        "time": frappe.utils.nowtime(),
        "message" : status_msg.get(str(status_code)),
        "uuid": uuid
        })

    log.save(ignore_permissions=True)

    if alert:
        frappe.msgprint(f"Failed, Status Code : {status_code}, <a href='/app/zatca-success-log/{log.name}' style='color: red;'>See Log</a>.", alert=1, indicator='red')
    else:
        return log.name
  