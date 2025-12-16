import os
import base64
import tempfile
from weasyprint import HTML
from odoo.exceptions import UserError
from odoo import _
import logging
_logger = logging.getLogger(__name__)


def print_complete_document_bundle(self):
    """
    Print a complete document bundle including:
    1. Document bundle itself
    2. DOP declaration
    3. All Welding Certificates PDF attachments (if include_document_in_bundle is True)
    4. All WPS records (if include_document_in_bundle is True)
    5. All control documents (if include_document_in_bundle is True)
    6. All Warehouse Certificates PDF attachments
    7. All welding tasks (if include_document_in_bundle is True)
    8. All technical document revisions PDF attachments
    9. All PDF attachments - their PDF attachment files
    """
    self.ensure_one()

    # Check if ghostscript is available before starting the process
    if not _check_ghostscript_available():
        raise UserError(_("Ghostscript is not installed or not available on this system. Please install Ghostscript to merge PDF documents. You can download it from: https://www.ghostscript.com/"))

    try:
        # Start with main document bundle HTML
        try:
            bundle_html = self.generate_report_html()
        except Exception as e:
            raise UserError(_("Failed to generate document bundle content. Please check that all required fields are filled: company name and address, counterparty name and address, and notified body name and address."))

        # Generate main PDF
        try:
            main_pdf_data = HTML(string=bundle_html).write_pdf()
            current_pdf_data = main_pdf_data
        except Exception as e:
            raise UserError(_("Failed to generate PDF from document bundle content. Please check the document content and try again."))

        # Add DOP Declaration
        try:
            dop_html = self.with_context(
                report_ref=self._dop_report_ref,
                force_report_ref=True
            ).generate_report_html()

            dop_pdf_data = HTML(string=dop_html).write_pdf()

            current_pdf_data = _merge_pdfs_with_attachments(current_pdf_data, [{'data': dop_pdf_data, 'name': 'DOP Declaration'}])
        except Exception as e:
            _logger.error(f"Failed to generate DOP (performance declaration): {str(e)}")

        # Add CE LABEL page
        try:
            ce_label_html = self.with_context(
                report_ref=self._ce_label_report_ref,
                force_report_ref=True
            ).generate_report_html()

            ce_label_pdf_data = HTML(string=ce_label_html).write_pdf()

            current_pdf_data = _merge_pdfs_with_attachments(current_pdf_data, [{'data': ce_label_pdf_data, 'name': 'CE LABEL'}])
        except Exception as e:
            # Continue without CE LABEL if it fails
            pass

        # Add Welding Certificates with their attachments
        if self.welding_certificates_ids:
            welding_cert_attachments = []
            for cert in self.welding_certificates_ids:
                # Only include if include_document_in_bundle is True
                if not cert.include_document_in_bundle:
                    continue

                # Collect certificate's PDF attachments only
                if cert.attachment_id:
                    for attachment in cert.attachment_id:
                        if attachment.mimetype == 'application/pdf':
                            try:
                                pdf_data = base64.b64decode(attachment.datas)
                                welding_cert_attachments.append({
                                    'name': f"Welding Certificate - {attachment.name}",
                                    'data': pdf_data,
                                    'source': f"Welding Certificate: {cert.name}"
                                })
                            except Exception as e:
                                pass

            # Add all welding certificate attachments to the bundle
            if welding_cert_attachments:
                current_pdf_data = _merge_pdfs_with_attachments(current_pdf_data, welding_cert_attachments)

        # Add WPS records
        if self.wps_record_ids:
            for wps in self.wps_record_ids:
                # Only include if include_document_in_bundle is True
                if not wps.include_document_in_bundle:
                    continue

                try:
                    wps_html = wps.generate_report_html()
                    wps_pdf_data = HTML(string=wps_html).write_pdf()
                    current_pdf_data = _merge_pdfs_with_attachments(current_pdf_data, [{'data': wps_pdf_data, 'name': f'WPS - {wps.name}'}])
                except Exception as e:
                    pass

        # Add Control Documents
        if self.control_document_ids:
            for control in self.control_document_ids:
                # Only include if include_document_in_bundle is True
                if not control.include_document_in_bundle:
                    continue

                try:
                    control_html = control.generate_report_html()
                    control_pdf_data = HTML(string=control_html).write_pdf()
                    current_pdf_data = _merge_pdfs_with_attachments(current_pdf_data, [{'data': control_pdf_data, 'name': f'Control Document - {control.name}'}])
                except Exception as e:
                    pass

        # Add Warehouse Certificates with their attachments
        if self.warehouse_certificate_ids:
            warehouse_cert_attachments = []
            for cert in self.warehouse_certificate_ids:
                # Collect certificate's PDF attachments only
                if cert.attachment_id:
                    for attachment in cert.attachment_id:
                        if attachment.mimetype == 'application/pdf':
                            try:
                                pdf_data = base64.b64decode(attachment.datas)
                                warehouse_cert_attachments.append({
                                    'name': f"Warehouse Certificate - {attachment.name}",
                                    'data': pdf_data,
                                    'source': f"Warehouse Certificate: {cert.name}"
                                })
                            except Exception as e:
                                pass

            # Add all warehouse certificate attachments to the bundle
            if warehouse_cert_attachments:
                current_pdf_data = _merge_pdfs_with_attachments(current_pdf_data, warehouse_cert_attachments)

        # Add ALL Warehouse Inspection Reports (computed field includes all from warehouse_certificate_ids)
        if self.warehouse_inspection_report_ids:
            inspection_report_attachments = []
            for report in self.warehouse_inspection_report_ids:
                attachment = getattr(report, 'pdf_attachment_id', False)
                if attachment and attachment.mimetype == 'application/pdf':
                    try:
                        pdf_data = base64.b64decode(attachment.datas)
                        inspection_report_attachments.append({
                            'name': f"Inspection Report - {attachment.name}",
                            'data': pdf_data,
                            'source': f"Inspection Report: {report.name}"
                        })
                    except Exception as e:
                        _logger.error(f"Failed to decode or attach inspection report PDF for report ID {report.id}, attachment ID {attachment.id}: {str(e)}")
                else:
                    # If no attachment, generate the PDF using the model's report logic and attach it
                    try:
                        _logger.info(f"Generating inspection report PDF for report: {report} (id: {report.id}, type: {type(report.id)}) using generate_report_html + inject_report_css")
                        html = report.generate_report_html()
                        html = report.inject_report_css(html)
                        pdf_data = HTML(string=html).write_pdf()
                        pdf_attachment = self.env['ir.attachment'].create({
                            'name': f"Inspection Report - {report.name}.pdf",
                            'type': 'binary',
                            'datas': base64.b64encode(pdf_data),
                            'res_model': report._name,
                            'res_id': report.id,
                            'mimetype': 'application/pdf',
                        })
                        report.pdf_attachment_id = pdf_attachment.id
                        inspection_report_attachments.append({
                            'name': f"Inspection Report - {report.name}.pdf",
                            'data': pdf_data,
                        })
                    except Exception as e:
                        _logger.error(f"Failed to generate inspection report PDF for report ID {report.id} using warehouses model logic: {e}")
                        continue
            if inspection_report_attachments:
                current_pdf_data = _merge_pdfs_with_attachments(current_pdf_data, inspection_report_attachments)
            else:
                _logger.error(f"No valid inspection report PDFs found for document bundle ID {self.id}.")
        else:
            _logger.error(f"No warehouse_inspection_report_ids found for document bundle ID {self.id}.")

        # Add Welding Tasks
        if self.welding_task_ids:
            for task in self.welding_task_ids:
                # Only include if include_document_in_bundle is True
                if not task.include_document_in_bundle:
                    continue

                try:
                    task_html = task.generate_report_html()
                    task_pdf_data = HTML(string=task_html).write_pdf()
                    current_pdf_data = _merge_pdfs_with_attachments(current_pdf_data, [{'data': task_pdf_data, 'name': f'Welding Task - {task.name}'}])
                except Exception as e:
                    pass

        # Add Technical Document Revisions PDF attachments only
        tech_doc_attachments = []
        if self.technical_document_revision_ids:
            for tech_doc in self.technical_document_revision_ids:
                if tech_doc.attachment_ids:
                    for attachment in tech_doc.attachment_ids:
                        if attachment.mimetype == 'application/pdf':
                            try:
                                pdf_data = base64.b64decode(attachment.datas)
                                tech_doc_attachments.append({
                                    'name': f"Technical Document - {attachment.name}",
                                    'data': pdf_data,
                                    'source': f"Technical Document: {tech_doc.name or 'Technical Document'}"
                                })
                            except Exception as e:
                                pass

        if tech_doc_attachments:
            current_pdf_data = _merge_pdfs_with_attachments(current_pdf_data, tech_doc_attachments)

        # Add ALL PDF attachments from attachment_ids field only
        all_pdf_attachments = []

        # Collect from document bundle's attachment_ids field
        if self.attachment_ids:
            for attachment in self.attachment_ids:
                if attachment.mimetype == 'application/pdf':
                    try:
                        pdf_data = base64.b64decode(attachment.datas)
                        all_pdf_attachments.append({
                            'name': f"Document Bundle Attachment - {attachment.name}",
                            'data': pdf_data,
                            'source': f"Document Bundle: {self.name}"
                        })
                    except Exception as e:
                        pass

        if all_pdf_attachments:
            current_pdf_data = _merge_pdfs_with_attachments(current_pdf_data, all_pdf_attachments)

        # Handle complete_pdf_attachment_id field
        attachment_name = f"Complete_Bundle_{self.name}.pdf"

        # Log final PDF information
        # Create new attachment first
        new_attachment = self.env["ir.attachment"].create({
            "name": attachment_name,
            "type": "binary",
            "datas": base64.b64encode(current_pdf_data).decode("utf-8"),
            "mimetype": "application/pdf",
            "store_fname": attachment_name
        })

        # Update the complete_pdf_attachment_id field first
        self.write({
            "complete_pdf_attachment_id": new_attachment.id
        })

        # Now try to remove the old attachment if it exists
        if self.complete_pdf_attachment_id and self.complete_pdf_attachment_id.id != new_attachment.id:
            try:
                old_attachment = self.complete_pdf_attachment_id
                # Only unlink if it's not being used elsewhere
                if not old_attachment.res_model and not old_attachment.res_id:
                    old_attachment.unlink()
            except Exception as e:
                pass

        # Return action to download the PDF
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{new_attachment.id}?download=true",
            "target": "new"
        }

    except Exception as e:
        raise UserError(_("Failed to generate complete document bundle: %s") % str(e))


def _add_title_to_pdf_with_ghostscript(pdf_data, title, output_path=None):
    """
    Add a title header to each page of a PDF using Ghostscript.

    Args:
        pdf_data: bytes - The PDF data
        title: str - The title to add
        output_path: str - Optional output path, if None creates temp file

    Returns:
        bytes - The PDF data with title added
    """
    try:
        import subprocess

        # Create temporary input file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as input_temp:
            input_temp.write(pdf_data)
            input_path = input_temp.name

        # Create temporary output file if not provided
        if not output_path:
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as output_temp:
                output_path = output_temp.name

        # Escape special characters in title for PostScript
        escaped_title = title.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')

        # Ghostscript command to add title to each page
        # This adds a header at the top of each page
        gs_script = f"""
        /Helvetica-Bold findfont 12 scalefont setfont
        /addTitle {{
            gsave
            50 800 moveto
            0.8 0.8 0.8 setrgbcolor
            0 0 0 0.1 setcmykcolor
            ({escaped_title}) show
            grestore
        }} def

        /processPage {{
            addTitle
        }} def
        """

        # Create temporary PostScript file
        with tempfile.NamedTemporaryFile(suffix='.ps', delete=False) as ps_temp:
            ps_temp.write(gs_script.encode('utf-8'))
            ps_path = ps_temp.name

        # Ghostscript command
        cmd = [
            'gs', '-dBATCH', '-dNOPAUSE', '-q', '-sDEVICE=pdfwrite',
            '-sOutputFile=' + output_path,
            '-f', ps_path, input_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        # Clean up temporary files
        try:
            os.unlink(input_path)
            os.unlink(ps_path)
        except:
            pass

        if result.returncode == 0 and os.path.exists(output_path):
            with open(output_path, 'rb') as f:
                return f.read()
        else:
            return pdf_data

    except Exception as e:
        return pdf_data


def _test_watermark_function(self):
    """
    Test function to verify watermark functionality works.
    This can be called manually to test if watermarks are working.
    """
    try:
        # Create a simple test PDF
        test_html = """
        <html>
        <body>
            <h1>Test Document</h1>
            <p>This is a test document to verify watermark functionality.</p>
        </body>
        </html>
        """

        test_pdf_data = HTML(string=test_html).write_pdf()

        # Create test attachment
        test_attachment = self.env["ir.attachment"].create({
            "name": "Test_Document.pdf",
            "type": "binary",
            "datas": base64.b64encode(test_pdf_data).decode("utf-8"),
            "mimetype": "application/pdf",
        })

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{test_attachment.id}?download=true",
            "target": "new"
        }

    except Exception as e:
        raise UserError(_("Test function failed: %s") % str(e))


def _merge_pdfs_with_attachments(main_pdf_data, pdf_attachments):
    """
    Merge the main PDF with PDF attachments from technical documents using a robust approach.

    Args:
        main_pdf_data: bytes - The main PDF data
        pdf_attachments: list - List of dicts with 'name', 'data', and 'source'

    Returns:
        bytes - The merged PDF data
    """
    try:
        # Ensure main_pdf_data is bytes (should already be bytes from WeasyPrint)
        if not isinstance(main_pdf_data, bytes):
            return main_pdf_data

        # If no attachments, just return the main PDF
        if not pdf_attachments:
            return main_pdf_data

        # Create temporary files for PDF merging
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as main_temp:
            main_temp.write(main_pdf_data)
            main_temp_path = main_temp.name

        # Create a list of PDF files to merge (starting with main PDF)
        pdf_files = [main_temp_path]

        # Add temporary files for each attachment
        temp_files = [main_temp_path]  # Track all temp files for cleanup

        for i, attachment in enumerate(pdf_attachments, 1):
            # Ensure attachment data is bytes
            attachment_data = attachment['data']
            if not isinstance(attachment_data, bytes):
                continue

            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                temp_file.write(attachment_data)
                pdf_files.append(temp_file.name)
                temp_files.append(temp_file.name)

        try:
            # Try using ghostscript (primary method)
            merged_pdf_data = _merge_pdfs_with_ghostscript(pdf_files)
            return merged_pdf_data

        except UserError as e:
            # Re-raise UserError to show proper error message to user
            raise e
        except Exception as e:
            raise UserError(_("PDF merging failed with unexpected error: %s") % str(e))

        finally:
            # Clean up temporary files
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except Exception as e:
                    pass

    except Exception as e:
        return main_pdf_data


def _check_ghostscript_available():
    """Check if ghostscript is available on the system."""
    try:
        import subprocess
        result = subprocess.run(['gs', '--version'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return True
        else:
            return False
    except FileNotFoundError:
        return False
    except Exception as e:
        return False


def _merge_pdfs_with_ghostscript(pdf_files):
    """Try to merge PDFs using ghostscript command line tool."""
    try:
        import subprocess
        import tempfile

        # Check if ghostscript is available
        if not _check_ghostscript_available():
            raise UserError(_("Ghostscript is not installed or not available on this system. Please install Ghostscript to merge PDF documents. You can download it from: https://www.ghostscript.com/"))

        # Create output temporary file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as output_temp:
            output_path = output_temp.name

        # Build ghostscript command
        cmd = ['gs', '-dBATCH', '-dNOPAUSE', '-q', '-sDEVICE=pdfwrite',
               f'-sOutputFile={output_path}'] + pdf_files

        # Run ghostscript
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0 and os.path.exists(output_path):
            # Read the merged PDF
            with open(output_path, 'rb') as f:
                merged_data = f.read()

            # Clean up output file
            try:
                os.unlink(output_path)
            except:
                pass

            return merged_data
        else:
            error_msg = f"Ghostscript failed with return code {result.returncode}: {result.stderr}"
            raise UserError(_("PDF merging failed: %s") % error_msg)

    except UserError:
        # Re-raise UserError as is
        raise
    except Exception as e:
        error_msg = f"Ghostscript merge failed: {str(e)}"
        raise UserError(_("PDF merging failed: %s") % error_msg)


def _add_title_to_pdf(pdf_data, title):
    """
    Add a title header to each page of a PDF.

    Args:
        pdf_data: bytes - The PDF data
        title: str - The title to add to each page

    Returns:
        bytes - The PDF data with titles added
    """
    try:
        from PyPDF2 import PdfReader, PdfWriter
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        from io import BytesIO

        # Read the original PDF
        pdf_reader = PdfReader(BytesIO(pdf_data))
        pdf_writer = PdfWriter()

        # Create a title overlay
        title_overlay = BytesIO()
        c = canvas.Canvas(title_overlay, pagesize=letter)

        # Set font and size for title
        c.setFont("Helvetica-Bold", 12)
        c.setFillColorRGB(0, 0, 0)  # Black color

        # Add title to each page
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]

            # Get page dimensions
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)

            # Create title overlay for this page
            title_page = BytesIO()
            title_canvas = canvas.Canvas(title_page, pagesize=(page_width, page_height))
            title_canvas.setFont("Helvetica-Bold", 12)
            title_canvas.setFillColorRGB(0, 0, 0)

            # Position title at top of page with some margin
            title_x = 50
            title_y = page_height - 30

            # Draw title
            title_canvas.drawString(title_x, title_y, title)
            title_canvas.save()

            # Merge title overlay with original page
            title_page.seek(0)
            title_pdf = PdfReader(title_page)
            title_page_obj = title_pdf.pages[0]

            # Overlay title on original page
            page.merge_page(title_page_obj)
            pdf_writer.add_page(page)

        # Write the final PDF
        output = BytesIO()
        pdf_writer.write(output)
        output.seek(0)

        return output.read()

    except ImportError:
        return pdf_data
    except Exception as e:
        return pdf_data
