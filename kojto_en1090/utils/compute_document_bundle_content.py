def compute_document_bundle_content(record):
    """
    Compute the HTML content for document bundle display.

    Args:
        record: The document bundle record

    Returns:
        str: HTML content for the document bundle
    """
    # Check if there are any documents in any category
    has_deliveries = bool(record.delivery_ids)
    has_wps = bool(record.wps_record_ids)
    has_control = bool(record.control_document_ids)
    has_welding_plans = bool(record.welding_task_ids)
    has_warehouse_certs = bool(record.warehouse_certificate_ids)
    has_welding_certs = bool(record.welding_certificates_ids)
    has_technical = bool(record.technical_document_revision_ids)
    has_pdf = bool(hasattr(record, 'pdf_document_ids') and record.pdf_document_ids)

    # Check if there is DOP content
    has_dop = bool(record.dop_signed_by or
                  record.dop_reaction_to_fire != 'class_a1' or
                  record.dop_cadmium_release != 'npd' or
                  record.dop_radioactivity_emission != 'npd')

    html_content = """
    <table class="performance-table" style="width: 100%; border-collapse: collapse; margin-top: 0; padding-top: 0;">
        <tbody>
    """

    # Header row with CONTENT
    html_content += """
        <tr>
            <td style="padding: 4px; ; width: 25%; background-color: #B0C4DE;"></td>
        </tr>
        <tr>
            <td style="padding: 4px; font-weight: bold; font-size: 120%; width: 25%; background-color: #B0C4DE;">CONTENT</td>
        </tr>
        <tr>
            <td style="padding: 4px; ; width: 25%; background-color: #B0C4DE;"></td>
        </tr>
    """

    # Always show DOP section first
    html_content += """
        <tr>
            <td style="padding: 4px; font-weight: bold; vertical-align: top; font-size: 110%; width: 25%; background-color: #B0C4DE;">Performance</td>
            <td style="padding: 4px; width: 75%;">Declaration of Performance (DOP) - EN 1090-1</td>
        </tr>
    """

    # Empty row after DOP
    html_content += """
        <tr>
            <td style="padding: 8px; width: 25%; background-color: #B0C4DE;"></td>
            <td style="padding: 8px; width: 75%;"></td>
        </tr>
    """

    # 1.0 Welding Certificates (if any)
    if has_welding_certs:
        html_content += """
            <tr>
                <td style="padding: 4px; font-weight: bold; vertical-align: top; font-size: 110%; width: 25%; background-color: #B0C4DE;" rowspan="{}">Welding Certificates</td>
        """.format(len(record.welding_certificates_ids))

        for idx, cert in enumerate(record.welding_certificates_ids, 1):
            cert_name = getattr(cert, 'name', getattr(cert, 'display_name', str(cert.id)))
            issuing_authority = getattr(cert, 'issuing_authority', '-')
            certificate_number = getattr(cert, 'certificate_number', '-')
            date_end = getattr(cert, 'date_end', '-')

            # Handle False values for all fields
            issuing_authority = '-' if not issuing_authority or issuing_authority == 'False' else issuing_authority
            certificate_number = '-' if not certificate_number or certificate_number == 'False' else certificate_number
            date_end = '-' if not date_end or date_end == 'False' else date_end

            # Format date if it exists and is not a dash
            if date_end != '-' and date_end:
                try:
                    date_end = date_end.strftime('%Y-%m-%d') if hasattr(date_end, 'strftime') else str(date_end)
                except:
                    date_end = '-'

            cert_details = f"{cert_name},  <strong>Issued:</strong> {issuing_authority}, Nr.: {certificate_number}, <strong>Valid Until:</strong> {date_end}"

            if idx == 1:
                html_content += f"""
                <td style="padding: 4px; width: 75%;">{cert_details}</td>
                </tr>
                """
            else:
                html_content += f"""
                <tr>
                <td style="padding: 4px; width: 75%;">{cert_details}</td>
                </tr>
                """

        # Empty row after Welding Certificates
        html_content += """
            <tr>
                <td style="padding: 8px; width: 25%; background-color: #B0C4DE;"></td>
                <td style="padding: 8px; width: 75%;"></td>
            </tr>
        """

    # 2.0 Deliveries
    if has_deliveries:
        html_content += """
            <tr>
                <td style="padding: 4px; font-weight: bold; vertical-align: top; font-size: 110%; width: 25%; background-color: #B0C4DE;" rowspan="{}">Deliveries</td>
        """.format(len(record.delivery_ids))

        for idx, delivery in enumerate(record.delivery_ids, 1):
            delivery_name = getattr(delivery, 'name', getattr(delivery, 'display_name', str(delivery.id)))
            if idx == 1:
                html_content += f"""
                <td style="padding: 4px; width: 75%;">{delivery_name}</td>
                </tr>
                """
            else:
                html_content += f"""
                <tr>
                <td style="padding: 4px; width: 75%;">{delivery_name}</td>
                </tr>
                """

        # Empty row after Deliveries
        html_content += """
            <tr>
                <td style="padding: 8px; width: 25%; background-color: #B0C4DE;"></td>
                <td style="padding: 8px; width: 75%;"></td>
            </tr>
        """

    # 3.0 Welding Procedure Specifications
    if has_wps:
        html_content += """
            <tr>
                <td style="padding: 4px; font-weight: bold; vertical-align: top; font-size: 110%; width: 25%; background-color: #B0C4DE;" rowspan="{}">WPS Records</td>
        """.format(len(record.wps_record_ids))

        for idx, wps in enumerate(record.wps_record_ids, 1):
            wps_name = getattr(wps, 'name', getattr(wps, 'display_name', str(wps.id)))
            name_secondary = getattr(wps, 'name_secondary', '')
            date_issue = getattr(wps, 'date_issue', None)
            # Format date_issue if it exists
            if date_issue:
                try:
                    date_issue_str = date_issue.strftime('%Y-%m-%d')
                except Exception:
                    date_issue_str = str(date_issue)
            else:
                date_issue_str = '-'
            # Compose details string
            details = wps_name
            if name_secondary:
                details += f" / {name_secondary}"
            details += f" / {date_issue_str}"
            if idx == 1:
                html_content += f"""
                <td style="padding: 4px; width: 75%;">{details}</td>
                </tr>
                """
            else:
                html_content += f"""
                <tr>
                <td style="padding: 4px; width: 75%;">{details}</td>
                </tr>
                """

        # Empty row after WPS Records
        html_content += """
            <tr>
                <td style="padding: 8px; width: 25%; background-color: #B0C4DE;"></td>
                <td style="padding: 8px; width: 75%;"></td>
            </tr>
        """

    # 4.0 Control Documents
    if has_control:
        html_content += """
            <tr>
                <td style="padding: 4px; font-weight: bold; vertical-align: top; font-size: 110%; width: 25%; background-color: #B0C4DE;" rowspan="{}">Control Documents</td>
        """.format(len(record.control_document_ids))

        for idx, control in enumerate(record.control_document_ids, 1):
            control_name = getattr(control, 'name', getattr(control, 'display_name', str(control.id)))
            if idx == 1:
                html_content += f"""
                <td style="padding: 4px; width: 75%;">{control_name}</td>
                </tr>
                """
            else:
                html_content += f"""
                <tr>
                <td style="padding: 4px; width: 75%;">{control_name}</td>
                </tr>
                """

        # Empty row after Control Documents
        html_content += """
            <tr>
                <td style="padding: 8px; width: 25%; background-color: #B0C4DE;"></td>
                <td style="padding: 8px; width: 75%;"></td>
            </tr>
        """

    # 5.0 Welding Plans
    if has_welding_plans:
        html_content += """
            <tr>
                <td style="padding: 4px; font-weight: bold; vertical-align: top; font-size: 110%; width: 25%; background-color: #B0C4DE;" rowspan="{}">Welding Plans</td>
        """.format(len(record.welding_task_ids))

        for idx, plan in enumerate(record.welding_task_ids, 1):
            plan_name = getattr(plan, 'name', getattr(plan, 'display_name', str(plan.id)))
            if idx == 1:
                html_content += f"""
                <td style="padding: 4px; width: 75%;">{plan_name}</td>
                </tr>
                """
            else:
                html_content += f"""
                <tr>
                <td style="padding: 4px; width: 75%;">{plan_name}</td>
                </tr>
                """

        # Empty row after Welding Plans
        html_content += """
            <tr>
                <td style="padding: 8px; width: 25%; background-color: #B0C4DE;"></td>
                <td style="padding: 8px; width: 75%;"></td>
            </tr>
        """

    # 6.0 Warehouse Certificates
    if has_warehouse_certs:
        html_content += """
            <tr>
                <td style="padding: 4px; font-weight: bold; vertical-align: top; font-size: 110%; width: 25%; background-color: #B0C4DE;" rowspan="{}">Warehouse Certificates</td>
        """.format(len(record.warehouse_certificate_ids))

        for idx, cert in enumerate(record.warehouse_certificate_ids, 1):
            cert_name = getattr(cert, 'name', getattr(cert, 'display_name', str(cert.id)))
            if idx == 1:
                html_content += f"""
                <td style="padding: 4px; width: 75%;">{cert_name}</td>
                </tr>
                """
            else:
                html_content += f"""
                <tr>
                <td style="padding: 4px; width: 75%;">{cert_name}</td>
                </tr>
                """

        # Empty row after Warehouse Certificates
        html_content += """
            <tr>
                <td style="padding: 8px; width: 25%; background-color: #B0C4DE;"></td>
                <td style="padding: 8px; width: 75%;"></td>
            </tr>
        """

    # 6.1 Inspection Reports (from warehouse_inspection_report_ids)
    inspection_reports = getattr(record, 'warehouse_inspection_report_ids', False)
    if inspection_reports:
        html_content += f"""
            <tr>
                <td style="padding: 4px; font-weight: bold; vertical-align: top; font-size: 110%; width: 25%; background-color: #B0C4DE;" rowspan="{len(inspection_reports)}">Inspection Reports</td>
        """
        for idx, report in enumerate(inspection_reports, 1):
            report_name = getattr(report, 'name', getattr(report, 'display_name', str(report.id)))
            if idx == 1:
                html_content += f"""
                <td style="padding: 4px; width: 75%;">{report_name}</td>
                </tr>
                """
            else:
                html_content += f"""
                <tr>
                <td style="padding: 4px; width: 75%;">{report_name}</td>
                </tr>
                """
        # Empty row after Inspection Reports
        html_content += """
            <tr>
                <td style="padding: 8px; width: 25%; background-color: #B0C4DE;"></td>
                <td style="padding: 8px; width: 75%;"></td>
            </tr>
        """

    # 7.0 Technical Documents
    if has_technical:
        html_content += """
            <tr>
                <td style="padding: 4px; font-weight: bold; vertical-align: top; font-size: 110%; width: 25%; background-color: #B0C4DE;" rowspan="{}">Technical Documents</td>
        """.format(len(record.technical_document_revision_ids))

        for idx, doc in enumerate(record.technical_document_revision_ids, 1):
            doc_name = getattr(doc, 'name', getattr(doc, 'display_name', str(doc.id)))
            if idx == 1:
                html_content += f"""
                <td style="padding: 4px; width: 75%;">{doc_name}</td>
                </tr>
                """
            else:
                html_content += f"""
                <tr>
                <td style="padding: 4px; width: 75%;">{doc_name}</td>
                </tr>
                """

        # Empty row after Technical Documents
        html_content += """
            <tr>
                <td style="padding: 8px; width: 25%; background-color: #B0C4DE;"></td>
                <td style="padding: 8px; width: 75%;"></td>
            </tr>
        """

    # 8.0 PDF Documents
    if has_pdf:
        html_content += """
            <tr>
                <td style="padding: 4px; font-weight: bold; vertical-align: top; font-size: 110%; width: 25%; background-color: #B0C4DE;" rowspan="{}">PDF Documents</td>
        """.format(len(record.pdf_document_ids))

        for idx, pdf in enumerate(record.pdf_document_ids, 1):
            pdf_name = getattr(pdf, 'name', getattr(pdf, 'display_name', str(pdf.id)))
            if idx == 1:
                html_content += f"""
                <td style="padding: 4px; width: 75%;">{pdf_name}</td>
                </tr>
                """
            else:
                html_content += f"""
                <tr>
                <td style="padding: 4px; width: 75%;">{pdf_name}</td>
                </tr>
                """

    html_content += """
        </tbody>
    </table>
    """

    return html_content
