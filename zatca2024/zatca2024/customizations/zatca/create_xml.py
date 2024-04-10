import re
import json
import frappe
from frappe import _
import uuid
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom

root_dir = frappe.get_site_path()

def create_plain_invoice(invoice, inv_type=None, compliance_type=0):
    setting = frappe.get_doc("Zatca setting")
    sp_party_add = frappe.get_doc("Address",invoice.company_address)
    sp_country_code = frappe.db.get_value("Country",sp_party_add.country,"code")
    cp_party_add = frappe.get_doc("Address",invoice.company_address)
    cp_country_code = frappe.db.get_value("Country",cp_party_add.country,"code")
    inv_note = "فاتورة مبيعات"
    uuid_str = str(uuid.uuid4())
    instruction_note = ""
    invoice_reference= ""
    payment_meams_code = "ZZZ" # ZZZ is for "Mutually defined" - code list => https://unece.org/fileadmin/DAM/trade/untdid/d16b/tred/tred4461.htm
    ubl_ext = get_ubl_ext()
    tax_cat_id, tax_exempt_reasoncode = get_tax_id(invoice)

    inv_typecode = 388 # For tax Invoice
    sub_typecode = 'name="0100000"' if inv_type == "B2B" else 'name="0200000"'
    if invoice.is_debit_note or compliance_type in ["5","6"]:
        # If Debit note
        inv_typecode = 383
        against = invoice.return_against if compliance_type == 0 else 654321
        invoice_reference = f"""
        <cac:BillingReference>
            <cac:InvoiceDocumentReference>
                <cbc:ID>{against}</cbc:ID>
            </cac:InvoiceDocumentReference>
        </cac:BillingReference>"""
        instruction_note = f"<cbc:InstructionNote>Rate Adjustment/Return</cbc:InstructionNote>"

    elif invoice.is_return or compliance_type in ["3","4"]:
        # If Credit note
        inv_typecode = 381
        against = invoice.return_against if compliance_type == 0 else 654321
        invoice_reference = f"""
        <cac:BillingReference>
            <cac:InvoiceDocumentReference>
                <cbc:ID>{against}</cbc:ID>
            </cac:InvoiceDocumentReference>
        </cac:BillingReference>"""
        instruction_note = f"<cbc:InstructionNote>Rate Adjustment/Return</cbc:InstructionNote>"

    with open(frappe.get_module_path("zatca2024")+"/customizations/zatca/xml_template/plain_invoice.xml","r") as file:
        invoice_temp = file.read()

    if invoice_temp:
        line_items = get_line_item(invoice)
        invoice_str = invoice_temp.format(
            # UBLExtensions
            UBL_EXTN = ubl_ext,
            # GaneralInfo
            INVOICE_NAME = invoice.name,
            UUID = uuid_str,
            POSTING_DATE = str(invoice.posting_date),
            POSTING_TIME = str(invoice.posting_time).split('.')[0],
            INV_TYPECOD = inv_typecode, #Need to check
            SUB_TYPECODE= sub_typecode,
            INV_NOTE = inv_note,
            INV_CURRENCY = invoice.currency,
            # BillingReference
            BILLING_REFERANCE= invoice_reference,
            # AdditionalDocumentReference
            PIH = setting.pih,
            ICV_UUID=re.sub(r'\D', '', invoice.name),
            QR_CODE = "",
            # AccountingSupplierParty
            SP_PARTY_ID = invoice.company_tax_id, #Need to check
            SP_STREET_NAME = sp_party_add.address_line2,
            SP_ADD_STREET_NAME = sp_party_add.additional_street_name,
            SP_BUILDING_NO = sp_party_add.address_line1,
            SP_PLOT_ID = sp_party_add.plot_identification,
            SP_CITY_SUBDIV = sp_party_add.city_sub_division,
            SP_CITY = sp_party_add.city,
            SP_POSTALZONE = sp_party_add.pincode,
            SP_COUNTRY_SUB = sp_party_add.state,
            SP_COUNTRY_ABBR = sp_country_code.upper(),
            COMPANY_VAT_NO = invoice.company_tax_id,
            COMPANY_NAME = invoice.company,
            # AccountingCustomerParty
            CP_STREET_NAME = cp_party_add.address_line2,
            CP_ADD_STREET_NAME = cp_party_add.additional_street_name,
            CP_BUILDING_NO = cp_party_add.address_line1,
            CP_PLOT_ID = cp_party_add.plot_identification,
            CP_CITY_SUBDIV = cp_party_add.city_sub_division,
            CP_CITY = cp_party_add.city,
            CP_POSTALZONE = cp_party_add.pincode,
            CP_COUNTRY_SUB = cp_party_add.state,
            CP_COUNTRY_ABBR = cp_country_code.upper(),
            CUS_VAT_NO = "",#invoice.tax_id,
            CUSTOMER_NAME = invoice.customer,
            # Delivery
            ACT_DELIVERY_DATE = str(invoice.posting_date),
            LST_DELIVERY_DATE = str(invoice.posting_date),
            # PaymentMeans
            PYM_MEANS_CODE = payment_meams_code,
            INSTRUCTION_NOTE = instruction_note,
            # TaxTotal
            TAX_AMOUNT = invoice.total_taxes_and_charges,
            TAXABLE_AMOUNT = invoice.total,
            TAX_CAT_ID = tax_cat_id, #Need to implement dynamic value for this
            TAX_EXEMPT_RESAON = tax_exempt_reasoncode,
            TAX_PERC = "5", # Need to check for mutiple tax rate in a invoice
            TAX_SCHEME = "VAT",
            # LegalMonetaryTotal
            LN_EXT_AMOUNT = invoice.total,
            TAX_EXC_AMOUNT = invoice.total,
            TAX_INC_AMOUNT = invoice.grand_total, # BT-112
            ALLOWANCE_AMOUNT = 0, #Need to check =
            CHARGE_AMOUNT = 0, #Need to check
            PRE_PAID_AMOUNT = invoice.total_advance, # BT-113
            PAYABLE_ROUNDING_AMOUNT = invoice.rounding_adjustment, # BT-114
            PAYABLE_AMOUNT = invoice.outstanding_amount, # BT-115 , Formula BT-115 = BT-112 - BT-113 + BT-114
            # InvoiceLine
            LINE_ITEMS = line_items
        )
        
    else:
        raise Exception("Xml template 'plain_invoice.xml' not found.")

    ET.register_namespace("xmlns","urn:oasis:names:specification:ubl:schema:xsd:Invoice-2")
    ET.register_namespace('cac',"urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2")
    ET.register_namespace('cbc',"urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2")
    ET.register_namespace('ds',"http://www.w3.org/2000/09/xmldsig#")
    ET.register_namespace('ext',"urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2")
    ET.register_namespace('sac',"urn:oasis:names:specification:ubl:schema:xsd:SignatureAggregateComponents-2")
    ET.register_namespace('sbc',"urn:oasis:names:specification:ubl:schema:xsd:SignatureBasicComponents-2")
    ET.register_namespace('sig',"urn:oasis:names:specification:ubl:schema:xsd:CommonSignatureComponents-2")
    ET.register_namespace('xades',"http://uri.etsi.org/01903/v1.3.2#")

    invoice_xml = ET.XML(invoice_str)
    invoice_xml.tag = "Invoice"
    invoice_xml.attrib['xmlns'] = 'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2'

    return invoice_xml, uuid_str

def get_line_item(invoice):
    items = ""
    for item in invoice.items:
        with open(frappe.get_module_path("zatca2024")+"/customizations/zatca/xml_template/invoice_line_items.xml","r") as file:
            item_xml = file.read()
        
        if item_xml:
            # If extra charges are there need to make CHARGES == True and following cbc tag
            # charge_resaoncode = <cbc:AllowanceChargeReasonCode>{reason_code}</cbc:AllowanceChargeReasonCode>
			# charge_reason_text = <cbc:AllowanceChargeReason>{reason_text}</cbc:AllowanceChargeReason>
            # Reason text and code will be found at https://unece.org/fileadmin/DAM/trade/untdid/d16b/tred/tred7161.htm
            charges = "false"
            charge_resaoncode = ""
            charge_reason_text = "<cbc:AllowanceChargeReason>discount</cbc:AllowanceChargeReason>"
            charge_amount = 0
            charge_percent = "" # If the charges are based on percent <cbc:MultiplierFactorNumeric>{percent_value}</cbc:MultiplierFactorNumeric>
            tax_details = None

            for tax in invoice.taxes:
                items_taxes = json.loads(tax.item_wise_tax_detail)
                crr_item_tax = items_taxes.get(item.item_code)
                if crr_item_tax:
                    tax_details = crr_item_tax
                    break
            rounding_amount = item.amount+tax_details[1] # BR-KSA-51

            if not tax_details:
                frappe.throw(_("Item tax details not found in the invoice."))

            items = items+item_xml.format(
                # GaneralInfo
                ITEM_IDX = item.idx,
                ITEM_QTY = item.qty,
                ITEM_EXT_AMOUNT = item.amount, # BT-131
                # TaxTotal
                TAX_AMOUNT = tax_details[1],
                ROUNDING_AMOUNT = rounding_amount,
                # Item
                ITEM_NAME = item.item_name,
                # Item-ClassifiedTaxCategory
                TAX_CAT = "S", # Need to check
                TAX_PERC = tax_details[0],
                TAX_SCHEME = "VAT",
                # Price
                PRICE_AMOUNT = item.rate, # BT-146
                BASE_QTY = item.qty,
                # AllowanceCharge
                CHARGE = charges,
                CHARGE_ALL_RESAONCODE = charge_resaoncode,
                CHARGE_ALL_RESAON = charge_reason_text,
                MULTI_FACTOR_NUMERIC = charge_percent, # Need to check
                CHARGE_AMOUNT = item.discount_amount, # BT-147
                BASE_AMOUNT = item.base_amount, # BT-148
            )
        else:
            raise Exception("Xml template 'invoice_line.xml' not found.")
    
    return items

def get_tax_id(invoice):
    # Reason if mandatory for the Different Tax Cat  
    #1. If Standard rate - Cat code = S:
    # tax_cat_id = "S"
    # tax_exempt_reasoncode = ""

    #2. Exempt from vat - cat code = E:
        # tax_exempt_reasoncode = "<cbc:TaxExemptionReasonCode>ReasonCodeIfApplicable</cbc:TaxExemptionReasonCode>
        # TAX_CAT_ID = "E"
        #And  this will need to add One of the reason code
        #1. VATEX-SA-29 - Financial services mentioned in Article 29 of the VAT Regulations
        #2. VATEX-SA-29-7 - Life insurance services mentioned in Article 29 of the VAT VAT
        #3. VATEX-SA-30 - Real estate transactions mentioned in Article 30 of the VAT Regulations

    #3. Zero Rated - Cat code = Z:
        # TAX_CAT_ID = "Z"
        # This will need to add one of the readon code
        # 1.VATEX-SA-32 - Export of goods
        # 2.VATEX-SA-33 - Export of services
        # 3. VATEX-SA-34-1 - The international transport of Goods
        # 4. VATEX-SA-34-2 - international transport of passengers
        # 5. VATEX-SA-34-3 - services directly connected and incidental to a Supply of international passenger transport
        # 6. VATEX-SA-34-4 - Supply of a qualifying means of transport
        # 7. VATEX-SA-34-5 - Any services relating to Goods or passenger transportation, as defined in article twenty five of these Regulations
        # 8. VATEX-SA-35 - Medicines and medical equipment 
        # 9. VATEX-SA-36 - Qualifying metals
        # 10. VATEX-SA-EDU - Private education to citizen
        # 11. VATEX-SA-HEA - Private healthcare to citizen
        # 12. VATEX-SA-MLTRY - supply of qualified military goods

    #4. Services outside scope of tax / Not subject to VAT -CAT code = O:
        # TAX_CAT_ID = O
        # 1. VATEX-SA-OOS - Reason is free text, to be provided by the taxpayer on case to case basis.
    
    return "S", ""

def get_ubl_ext():
    """
    Adding ubl format only, the values will be auto calculated and filled by sdk
    """
    with open(frappe.get_module_path("zatca2024")+"/customizations/zatca/xml_template/ubl_extension.xml","r") as file:
        ubl_ext = file.read()

    if ubl_ext:
        with open (root_dir+"/cert.pem","r") as file:
            cert = file.read()
        if not cert:
            raise Exception("Certificate not found.")
        ubl = ubl_ext.format(
            TRF_DIGEST="",
            KEYINFO_CERT="",
            REF_DIGEST="",
            SIGN_VALUE="",
            CERT_DIGEST="",
            ISSUER_NAME="",
            ISSUER_SERIAL_NO="",
        )
        return ubl
        
def xml_structuring(invoice,sales_invoice_doc):
    # try:
        # xml_declaration = "<?xml version='1.0' encoding='UTF-8'?>\n"
        tree = ET.ElementTree(invoice)
        with open(f"invoice.xml", 'wb') as file:
            tree.write(file, encoding='utf-8', xml_declaration=True)

        if frappe.db.get_single_value("Zatca setting","attach_xml_with_invoice"):
            with open(f"invoice.xml", 'r') as file:
                xml_string = file.read()
            # xml_dom = minidom.parseString(xml_string)
            # pretty_xml_string = xml_dom.toprettyxml(indent=1)   # created xml into formatted xml form 
            # with open(f"finalzatcaxml.xml", 'w') as file:
            #     file.write(pretty_xml_string)
                        # Attach the getting xml for each invoice
            # try:
            if frappe.db.exists("File",{ "attached_to_name": sales_invoice_doc.name, "attached_to_doctype": sales_invoice_doc.doctype }):
                frappe.db.delete("File",{ "attached_to_name":sales_invoice_doc.name, "attached_to_doctype": sales_invoice_doc.doctype })
            # except Exception as e:
                # frappe.throw(frappe.get_traceback())
            
            # try:
            fileX = frappe.get_doc(
                {   "doctype": "File",
                    "file_type": "xml",
                    "file_name":  "E-invoice-" + sales_invoice_doc.name + ".xml",
                    "attached_to_doctype":sales_invoice_doc.doctype,
                    "attached_to_name":sales_invoice_doc.name,
                    "content": xml_string,
                    "is_private": 1,})
            fileX.save()
        
        # try:
        #     frappe.db.get_value('File', {'attached_to_name':sales_invoice_doc.name, 'attached_to_doctype': sales_invoice_doc.doctype}, ['file_name'])
        # except Exception as e:
        #     frappe.throw(frappe.get_traceback())
    # except Exception as e:
    #         frappe.throw("Error occured in XML structuring and attach. Please contact your system administrator"+ str(e) )


