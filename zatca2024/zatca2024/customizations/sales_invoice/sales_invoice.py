import frappe
from zatca2024.zatca2024.customizations.zatca.zatcasdkcode import zatca_Background_on_submit

def before_save(doc, method=None):
    if doc.custom_zatca_status in ("REPORTED", "CLEARED"):
        frappe.throw("This invoice is already submitted to ZATCA. You cannot edit, cancel or save it.")

def after_insert(doc, method=None):
    # required on version 13  as no-copy settings on fields not available
    # frappe.msgprint(frappe.__version__)
    # frappe.msgprint(int(frappe.__version__.split('.')[0]))
    if int(frappe.__version__.split('.')[0]) == 13:
        frappe.msgprint("duplicating invoice")
        doc.custom_uuid = "Not submitted"
        doc.custom_zatca_status = "Not Submitted"
        doc.save()

def on_submit(doc, method=None):
    if frappe.db.get_single_value("Zatca setting","send_invoice_to_zatca") == "On Submit":
        zatca_Background_on_submit(invoice_doc=doc)

def before_cancel(doc, method=None):
    if doc.custom_zatca_status in ("REPORTED", "CLEARED"):
        frappe.throw("This invoice is already submitted to ZATCA. You cannot edit, cancel or save it.")

def before_submit(doc, method=None):
    if doc.custom_zatca_status != "REPORTED" and doc.custom_zatca_status != "CLEARED":
        frappe.throw("Please send this invoice to ZATCA, before submitting")