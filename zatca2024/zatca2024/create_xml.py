import json
import frappe
import uuid
import xml.etree.ElementTree as ET

def create_plain_invoice(invoice, inv_type=None, compliance_type=0):
    setting = frappe.get_doc("Zatca setting")
    sp_party_add = frappe.get_doc("Address",invoice.company_address)
    sp_country_code = frappe.db.get_value("Country",sp_party_add.country,"code")
    cp_party_add = frappe.get_doc("Address",invoice.company_address)
    cp_country_code = frappe.db.get_value("Country",cp_party_add.country,"code")
    inv_note = "فاتورة مبيعات"
    uuid_str = str(uuid.uuid4())
    ubl_ext = get_ubl_ext()
    inv_typecode = 388 # For tax Invoice
    sub_typecode = 'name="0100000"' if inv_type == "B2B" else 'name="0200000"'
    instruction_note = ""
    invoice_reference= ""

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

    # Reason if mandatory for the Different Tax Cat  
    #1. If Standard rate - Cat code = S:
    tax_cat_id = "S"
    tax_exempt_reasoncode = ""

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

    # Payment means code should be provided from the list of https://unece.org/fileadmin/DAM/trade/untdid/d16b/tred/tred4461.htm
    # ZZZ is for "Mutually defined" - desc = "A code assigned within a code list to be used on an interim basis and as defined among trading partners until a precise code can be assigned to the code list."
    
    payment_meams_code = "ZZZ"

    with open(frappe.get_app_path("zatca2024")+"/zatca2024/xml_template/plain_invoice.xml","r") as file:
        invoice_temp = file.read()

    if invoice_temp:
        line_items = get_line_item(invoice)
        invoice_str = invoice_temp.format(
            UBL_EXTN = ubl_ext,
            QR_CODE = "",
            BILLING_REFERANCE= invoice_reference,
            INVOICE_NAME = invoice.name,
            UUID = uuid_str,
            POSTING_DATE = str(invoice.posting_date),
            POSTING_TIME = str(invoice.posting_time).split('.')[0],
            INV_TYPECOD = inv_typecode, #Need to check
            SUB_TYPECODE= sub_typecode,
            INV_NOTE = inv_note,
            INV_CURRENCY = invoice.currency,
            PIH = setting.pih,
            ICV_UUID='00006',
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
            ACT_DELIVERY_DATE = str(invoice.posting_date),# Delivery date was on SO need to check the flow,
            LST_DELIVERY_DATE = str(invoice.posting_date), # Need to check
            PYM_MEANS_CODE = payment_meams_code, # Need to check,
            INSTRUCTION_NOTE = instruction_note,
            TAX_AMOUNT = invoice.total_taxes_and_charges,
            TAXABLE_AMOUNT = invoice.total,
            TAX_CAT_ID = tax_cat_id, #Need to implement dynamic value for this
            TAX_EXEMPT_RESAON = tax_exempt_reasoncode,
            TAX_PERC = "5", #Need to check for mutiple tax rate in a invoice
            TAX_SCHEME = "VAT",
            LN_EXT_AMOUNT = invoice.total,
            TAX_EXC_AMOUNT = invoice.total,
            TAX_INC_AMOUNT = invoice.grand_total, # BT-112
            ALLOWANCE_AMOUNT = 0, #Need to check =
            CHARGE_AMOUNT = 0, #Need to check
            PRE_PAID_AMOUNT = invoice.total_advance, # BT-113
            PAYABLE_ROUNDING_AMOUNT = invoice.rounding_adjustment, # BT-114
            PAYABLE_AMOUNT = invoice.outstanding_amount, # BT-115 , Formula BT-115 = BT-112 - BT-113 + BT-114
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

    # print("this===>",invoice_str)
    # invoice = ET.Element("Invoice", xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" )
    # invoice.set("xmlns:cac", "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2")
    # invoice.set("xmlns:cbc", "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2")
    # invoice.set("xmlns:ds", "http://www.w3.org/2000/09/xmldsig#")
    # invoice.set("xmlns:ext", "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2")
    # invoice.set("xmlns:sac", "urn:oasis:names:specification:ubl:schema:xsd:SignatureAggregateComponents-2")
    # invoice.set("xmlns:sbc", "urn:oasis:names:specification:ubl:schema:xsd:SignatureBasicComponents-2")
    # invoice.set("xmlns:sig", "urn:oasis:names:specification:ubl:schema:xsd:CommonSignatureComponents-2")
    # invoice.set("xmlns:xades", "http://uri.etsi.org/01903/v1.3.2#")
    # invoice_xml.tag = "invoice urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
    # print(f"\n\n\n\n{invoice_xml.tag}\n\n\n")
    # print(f"\n\n\nXML=>{invoice_xml}\n\n\n")
    # print(f"\n\n\nInvoice after =>{ET.tostring(invoice_xml, encoding='unicode',method='xml')}\n\n\n")
    # root = invoice_xml.getroot()
    # invoice_xml = ET.fromstring(ubl_ext)
    # invoice_xml = ET.SubElement(invoice,ubl_ext)
    # invoice_xml = ET.parse(os.getcwd()+"/asif.xml")
    # root = invoice_xml.getroot()
    # qr_code_hash = get_qr_code(invoice)

def get_line_item(invoice):
    items = ""
    for item in invoice.items:
        with open(frappe.get_app_path("zatca2024")+"/zatca2024/xml_template/invoice_line_items.xml","r") as file:
            item_xml = file.read()
        
        if item_xml:
            #If extra charges are there need to make CHARGES == True and following cbc tag
            # charge_resaoncode = <cbc:AllowanceChargeReasonCode>{reason_code}</cbc:AllowanceChargeReasonCode>
			# charge_reason_text = <cbc:AllowanceChargeReason>{reason_text}</cbc:AllowanceChargeReason>
            # Reason text and code will be found at https://unece.org/fileadmin/DAM/trade/untdid/d16b/tred/tred7161.htm
            charges = "true"
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
                frappe.throw("Item tax details not found in the invoice.")

            items = items+item_xml.format(
                ITEM_IDX = item.idx,
                ITEM_QTY = item.qty,
                ITEM_NAME = item.item_name,
                TAX_CAT = "S", # Need to check
                TAX_PERC = tax_details[0],
                TAX_SCHEME = "VAT",
                TAX_AMOUNT = tax_details[1],
                ITEM_EXT_AMOUNT = item.amount, # BT-131
                BASE_QTY = item.qty,
                ROUNDING_AMOUNT = rounding_amount,
                PRICE_AMOUNT = item.rate, # BT-146
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

def get_ubl_ext():
    with open(frappe.get_app_path("zatca2024")+"/zatca2024/xml_template/ubl_extension.xml","r") as file:
        ubl_ext = file.read()

    if ubl_ext:
        with open ("cert.pem","r") as file:
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
        
