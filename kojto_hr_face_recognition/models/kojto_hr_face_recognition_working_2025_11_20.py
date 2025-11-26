from odoo import api, fields, models
from datetime import datetime, timedelta
from odoo.exceptions import UserError, ValidationError, AccessDenied
from io import BytesIO
from PIL import Image
import pytz
import base64
import numpy as np
import face_recognition
from odoo.tools import config
import json
import os


class KojtoHrTimeTrackingImage(models.Model):
    _name = "kojto.hr.face.recognition"
    _description = "Kojto HR Time Tracking Image"
    _order = "datetime_taken desc"
    _rec_name = "name"

    name = fields.Char(string="Name", compute="_compute_name", store=True)
    image = fields.Binary(string="Image")
    face_encoding = fields.Text(string="Face Encoding", help="JSON representation of face encoding")
    datetime_taken = fields.Datetime(string="Date/Time Taken")
    employee_id = fields.Many2one("kojto.hr.employees", string="Employee")
    user_id = fields.Many2one(related="employee_id.user_id", string="Associated User")


    @api.model_create_multi
    def create(self, vals_list):
        # Only create records that have an image
        valid_vals = [vals for vals in vals_list if vals.get('image')]

        if not valid_vals:
            # Don't create empty records
            return self.env['kojto.hr.face.recognition']

        records = super(KojtoHrTimeTrackingImage, self).create(valid_vals)
        records.action_assign_employee_by_face_recognition()
        return records

    def write(self, vals):
        result = super(KojtoHrTimeTrackingImage, self).write(vals)
        if "image" in vals:
            self.action_assign_employee_by_face_recognition()
        return result

    @api.depends("datetime_taken", "employee_id", "image")
    def _compute_name(self):
        for record in self:
            record.name = f"Time Tracking for {record.employee_id.name if record.employee_id else 'Unknown Employee'}"

    def action_assign_employee_by_face_recognition(self):
        for record in self:
            if not record.image:
                return

            record.datetime_taken = fields.Datetime.now()

            base_images = self.env["kojto.base.images"].search([
                ("employee_id", "!=", False),
                ("employee_id.active", "=", True)
            ])
            employee_encodings = {}
            db_name = self.env.cr.dbname
            filestore_path = config.filestore(db_name)
            for base_image in base_images:
                encoding = None
                if base_image.face_encoding:
                    try:
                        encoding = np.array(json.loads(base_image.face_encoding))
                    except Exception:
                        encoding = None
                if encoding is None:
                    # Try to retrieve the image from the filestore (same as working version)
                    try:
                        attachment = self.env['ir.attachment'].search([
                            ("res_model", "=", "kojto.base.images"),
                            ("res_id", "=", base_image.id),
                            ("res_field", "=", "image")
                        ], limit=1)
                        if not attachment or not attachment.store_fname:
                            raise Exception("No attachment or store_fname")
                        file_path = os.path.join(filestore_path, attachment.store_fname)
                        if not os.path.exists(file_path):
                            raise Exception("File does not exist in filestore")
                        # Read the file and encode
                        with open(file_path, "rb") as f:
                            file_data = f.read()
                        img = Image.open(BytesIO(file_data)).convert("RGB")

                        # Use face detection with better sensitivity for more lenient matching
                        face_locations = face_recognition.face_locations(np.array(img), model="hog", number_of_times_to_upsample=1)
                        encodings = face_recognition.face_encodings(np.array(img), face_locations)

                        if encodings:
                            # Validate that only one face is present
                            if len(encodings) > 1:
                                raise Exception(f"Multiple faces detected in employee image - {len(encodings)} faces found. Only one face per image is allowed.")

                            # Use the single face encoding
                            encoding = encodings[0]
                            base_image.face_encoding = json.dumps(encoding.tolist())
                        else:
                            raise Exception("No face found in image")
                    except Exception as e:
                        # Log and delete orphaned image
                        self.env["ir.logging"].create({
                            "name": "Face Recognition Error",
                            "type": "server",
                            "message": f"Orphaned base image {base_image.id} deleted: {e}",
                            "path": __name__,
                            "func": "action_assign_employee_by_face_recognition",
                            "line": 0,
                        })
                        base_image.unlink()
                        continue
                if encoding is not None:
                    employee_encodings.setdefault(base_image.employee_id.id, []).append(encoding)

            match_found = False
            for record in self:
                if record.employee_id or not record.image:
                    continue
                try:
                    # Process tracking image directly like working version
                    img = Image.open(BytesIO(base64.b64decode(record.image))).convert("RGB")

                    # Use face detection with better sensitivity for tracking images (same as working version)
                    face_locations = face_recognition.face_locations(np.array(img), model="hog", number_of_times_to_upsample=1)
                    tracking_encodings = face_recognition.face_encodings(np.array(img), face_locations)

                    if not tracking_encodings:
                        self.env["ir.logging"].create({
                            "name": "Face Recognition Warning",
                            "type": "server",
                            "message": f"No face found in tracking image {record.id}",
                            "path": __name__,
                            "func": "action_assign_employee_by_face_recognition",
                            "line": 0,
                        })
                        continue

                    # Validate that only one face is present in tracking image (same as working version)
                    if len(tracking_encodings) > 1:
                        self.env["ir.logging"].create({
                            "name": "Face Recognition Warning",
                            "type": "server",
                            "message": f"Multiple faces detected in tracking image {record.id} - {len(tracking_encodings)} faces found. Only one face per image is allowed.",
                            "path": __name__,
                            "func": "action_assign_employee_by_face_recognition",
                            "line": 0,
                        })
                        continue

                    # Use the single face encoding (same as working version)
                    tracking_encoding = tracking_encodings[0]

                    # Store the face encoding for future reference
                    record.face_encoding = json.dumps(tracking_encoding.tolist())
                    best_match_employee = None
                    best_match_distance = float('inf')
                    best_match_confidence = 0.0

                    # Compare with ALL employee encodings to find the BEST match (same as working version)
                    for employee_id, encodings_list in employee_encodings.items():
                        # Calculate face distance for each employee encoding
                        for employee_encoding in encodings_list:
                            # Use face_distance for more precise comparison
                            face_distance = face_recognition.face_distance([employee_encoding], tracking_encoding)[0]

                            # Lower distance = better match
                            if face_distance < best_match_distance:
                                best_match_distance = face_distance
                                best_match_employee = employee_id
                                # Convert distance to confidence percentage (lower distance = higher confidence)
                                best_match_confidence = max(0, (1 - face_distance) * 100)

                    # Use simplified validation logic similar to working version
                    minimum_confidence_threshold = 40.0  # Back to working version threshold

                    # Log debug information
                    self.env["ir.logging"].create({
                        "name": "Face Recognition Debug Info",
                        "type": "server",
                        "message": f"Processing tracking image {record.id} - Best match: Employee {best_match_employee} (Distance: {best_match_distance:.3f}, Confidence: {best_match_confidence:.1f}%)",
                        "path": __name__,
                        "func": "action_assign_employee_by_face_recognition",
                        "line": 0,
                    })

                    # Simple validation: just check minimum confidence threshold
                    if best_match_employee and best_match_confidence >= minimum_confidence_threshold:
                        record.employee_id = best_match_employee
                        match_found = True

                        # Log successful match with confidence
                        self.env["ir.logging"].create({
                            "name": "Face Recognition Success",
                            "type": "server",
                            "message": f"Best match found for tracking image {record.id} -> Employee {best_match_employee} (Confidence: {best_match_confidence:.1f}%)",
                            "path": __name__,
                            "func": "action_assign_employee_by_face_recognition",
                            "line": 0,
                        })

                    if not match_found:
                        # Try fallback method with more lenient tolerance for false negatives (same as working version)
                        # Use the same "best match" approach for fallback
                        fallback_best_match = None
                        fallback_best_distance = float('inf')

                        for employee_id, encodings_list in employee_encodings.items():
                            for employee_encoding in encodings_list:
                                face_distance = face_recognition.face_distance([employee_encoding], tracking_encoding)[0]
                                if face_distance < fallback_best_distance:
                                    fallback_best_distance = face_distance
                                    fallback_best_match = employee_id

                        # Use a more lenient threshold for fallback (same as working version)
                        if fallback_best_match and fallback_best_distance < 0.7:
                            record.employee_id = fallback_best_match
                            match_found = True
                            fallback_confidence = max(0, (1 - fallback_best_distance) * 100)

                            # Log fallback match
                            self.env["ir.logging"].create({
                                "name": "Face Recognition Fallback Match",
                                "type": "server",
                                "message": f"Fallback match found for tracking image {record.id} -> Employee {fallback_best_match} (Distance: {fallback_best_distance:.3f}, Confidence: {fallback_confidence:.1f}%)",
                                "path": __name__,
                                "func": "action_assign_employee_by_face_recognition",
                                "line": 0,
                            })

                    if not match_found:
                        # Log that no match was found but keep the record
                        self.env["ir.logging"].create({
                            "name": "Face Recognition Warning",
                            "type": "server",
                            "message": f"No face match found for tracking image {record.id}. Record kept for manual review.",
                            "path": __name__,
                            "func": "action_assign_employee_by_face_recognition",
                            "line": 0,
                        })
                        # Don't delete the record, let it remain for manual assignment

                except Exception as e:
                    self.env["ir.logging"].create({
                        "name": "Face Recognition Error",
                        "type": "server",
                        "message": f"Error processing tracking image {record.id}: {e}",
                        "path": __name__,
                        "func": "action_assign_employee_by_face_recognition",
                        "line": 0,
                    })

            if match_found:
                self.check_employee_id()

    def check_employee_id(self):
        for record in self:
            if not record.employee_id:
                raise UserError(f"No employee assigned to time tracking image ID {record.id}. " "Face recognition could not match an employee.")
       # self.action_update_time_tracking()

    def action_update_time_tracking(self):
        time_tracking_model = self.env["kojto.hr.time.tracking"]

        for record in self:
            if not record.employee_id or not record.datetime_taken:
                continue

            last_tracking = time_tracking_model.search(
                [("employee_id", "=", record.employee_id.id)],
                order="datetime_start desc",
                limit=1,
            )

            if last_tracking and not last_tracking.datetime_end:
                last_tracking.write({"datetime_end": record.datetime_taken})

            else:
                last_time_tracking = time_tracking_model.search([
                    ("employee_id", "=", record.employee_id.id),
                    ("datetime_end", "!=", False)
                ], order="datetime_start desc", limit=1)

                time_tracking_model.create(
                    [
                        {
                            "employee_id": record.employee_id.id,
                            "datetime_start": record.datetime_taken,
                            "subcode_id": last_time_tracking.subcode_id.id if last_time_tracking else self.env["kojto.commission.subcodes"].search([], limit=1).id,
                        }
                    ]
                )

    #def create_and_open_new_image_record(self):
    #    new_image_record = self.env["kojto.hr.face.recognition"].create({})

    #    return {
    #        "type": "ir.actions.act_window",
    #        "res_model": "kojto.hr.face.recognition",
    #        "res_id": new_image_record.id,
    #        "view_mode": "form",
    #        "target": "current",
    #    }

    @api.model
    def open_terminal(self):
        """Opens the terminal"""
        # Find the most recent record (within last 30 seconds) to show feedback
        thirty_seconds_ago = fields.Datetime.now() - timedelta(seconds=30)
        recent_record = self.search([
            ('datetime_taken', '>=', thirty_seconds_ago)
        ], order='datetime_taken desc', limit=1)

        if recent_record:
            # Show the recent result (success/error feedback)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Terminal',
                'res_model': 'kojto.hr.face.recognition',
                'view_mode': 'form',
                'res_id': recent_record.id,
                'target': 'current',
            }
        else:
            # If no recent record, check for any record
            any_record = self.search([], order='id desc', limit=1)
            if any_record:
                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Terminal',
                    'res_model': 'kojto.hr.face.recognition',
                    'view_mode': 'form',
                    'res_id': any_record.id,
                    'target': 'current',
                }
            else:
                # No records exist - return notification to use camera
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'No Records',
                        'message': 'Please click the camera icon in the image field to capture your first photo.',
                        'type': 'info',
                        'sticky': True,
                        'next': {
                            'type': 'ir.actions.act_window',
                            'name': 'Time Tracking Images',
                            'res_model': 'kojto.hr.face.recognition',
                            'view_mode': 'list',
                            'target': 'current',
                        },
                    }
                }

    def record_datetime(self):
        """Called when camera button is clicked"""
        # Just return True - the JavaScript onclick will handle opening the camera
        return True

    def action_recalculate_all_face_encodings(self):
        """Recalculate face encodings for all employee images"""
        # Get all base images that have an employee_id and an image (including inactive employees)
        base_images = self.env["kojto.base.images"].search([
            ("employee_id", "!=", False),
            ("image", "!=", False)
        ])

        if not base_images:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Images Found',
                    'message': 'No employee images found to process.',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        processed_count = 0
        error_count = 0
        db_name = self.env.cr.dbname
        filestore_path = config.filestore(db_name)

        for base_image in base_images:
            try:
                # Try to retrieve the image from the filestore
                attachment = self.env['ir.attachment'].search([
                    ("res_model", "=", "kojto.base.images"),
                    ("res_id", "=", base_image.id),
                    ("res_field", "=", "image")
                ], limit=1)

                if not attachment or not attachment.store_fname:
                    self.env["ir.logging"].create({
                        "name": "Face Encoding Recalculation Error",
                        "type": "server",
                        "message": f"No attachment or store_fname for base image {base_image.id}",
                        "path": __name__,
                        "func": "action_recalculate_all_face_encodings",
                        "line": 0,
                    })
                    error_count += 1
                    continue

                file_path = os.path.join(filestore_path, attachment.store_fname)
                if not os.path.exists(file_path):
                    self.env["ir.logging"].create({
                        "name": "Face Encoding Recalculation Error",
                        "type": "server",
                        "message": f"File does not exist in filestore for base image {base_image.id}: {file_path}",
                        "path": __name__,
                        "func": "action_recalculate_all_face_encodings",
                        "line": 0,
                    })
                    error_count += 1
                    continue

                # Read the file and encode
                with open(file_path, "rb") as f:
                    file_data = f.read()

                img = Image.open(BytesIO(file_data)).convert("RGB")

                # Use face detection with better sensitivity for recalculation
                face_locations = face_recognition.face_locations(np.array(img), model="hog", number_of_times_to_upsample=1)
                encodings = face_recognition.face_encodings(np.array(img), face_locations)

                if encodings:
                    # Validate that only one face is present
                    if len(encodings) > 1:
                        self.env["ir.logging"].create({
                            "name": "Face Encoding Validation Error",
                            "type": "server",
                            "message": f"Multiple faces detected in base image {base_image.id} (Employee: {base_image.employee_id.name}) - {len(encodings)} faces found. Only one face per image is allowed.",
                            "path": __name__,
                            "func": "action_recalculate_all_face_encodings",
                            "line": 0,
                        })
                        error_count += 1
                        continue

                    # Use the single face encoding
                    encoding = encodings[0]
                    base_image.face_encoding = json.dumps(encoding.tolist())
                    processed_count += 1

                    self.env["ir.logging"].create({
                        "name": "Face Encoding Success",
                        "type": "server",
                        "message": f"Successfully processed base image {base_image.id} (Employee: {base_image.employee_id.name}) - single face detected",
                        "path": __name__,
                        "func": "action_recalculate_all_face_encodings",
                        "line": 0,
                    })
                else:
                    self.env["ir.logging"].create({
                        "name": "Face Encoding Recalculation Warning",
                        "type": "server",
                        "message": f"No face found in image for base image {base_image.id} (Employee: {base_image.employee_id.name})",
                        "path": __name__,
                        "func": "action_recalculate_all_face_encodings",
                        "line": 0,
                    })
                    error_count += 1

            except Exception as e:
                # Handle specific error types
                error_msg = str(e)
                if "Multiple faces detected" in error_msg:
                    # Try to delete invalid image, but handle permission errors gracefully
                    try:
                        base_image.unlink()
                        self.env["ir.logging"].create({
                            "name": "Face Encoding Cleanup",
                            "type": "server",
                            "message": f"Successfully removed invalid base image {base_image.id} (Employee: {base_image.employee_id.name}) - multiple faces",
                            "path": __name__,
                            "func": "action_recalculate_all_face_encodings",
                            "line": 0,
                        })
                    except AccessDenied:
                        self.env["ir.logging"].create({
                            "name": "Face Encoding Permission Warning",
                            "type": "server",
                            "message": f"Skipped deletion of invalid base image {base_image.id} (Employee: {base_image.employee_id.name}) - user lacks delete permissions. Manual cleanup may be required.",
                            "path": __name__,
                            "func": "action_recalculate_all_face_encodings",
                            "line": 0,
                        })
                    except Exception as delete_error:
                        self.env["ir.logging"].create({
                            "name": "Face Encoding Delete Error",
                            "type": "server",
                            "message": f"Failed to delete invalid base image {base_image.id} (Employee: {base_image.employee_id.name}): {delete_error}",
                            "path": __name__,
                            "func": "action_recalculate_all_face_encodings",
                            "line": 0,
                        })

                elif "No face found" in error_msg:
                    # Try to delete image with no face, but handle permission errors gracefully
                    try:
                        base_image.unlink()
                        self.env["ir.logging"].create({
                            "name": "Face Encoding Cleanup",
                            "type": "server",
                            "message": f"Successfully removed invalid base image {base_image.id} (Employee: {base_image.employee_id.name}) - no face detected",
                            "path": __name__,
                            "func": "action_recalculate_all_face_encodings",
                            "line": 0,
                        })
                    except AccessDenied:
                        self.env["ir.logging"].create({
                            "name": "Face Encoding Permission Warning",
                            "type": "server",
                            "message": f"Skipped deletion of invalid base image {base_image.id} (Employee: {base_image.employee_id.name}) - user lacks delete permissions. Manual cleanup may be required.",
                            "path": __name__,
                            "func": "action_recalculate_all_face_encodings",
                            "line": 0,
                        })
                    except Exception as delete_error:
                        self.env["ir.logging"].create({
                            "name": "Face Encoding Delete Error",
                            "type": "server",
                            "message": f"Failed to delete invalid base image {base_image.id} (Employee: {base_image.employee_id.name}): {delete_error}",
                            "path": __name__,
                            "func": "action_recalculate_all_face_encodings",
                            "line": 0,
                        })

                else:
                    # Log generic error
                    self.env["ir.logging"].create({
                        "name": "Face Encoding Recalculation Error",
                        "type": "server",
                        "message": f"Error processing base image {base_image.id} (Employee: {base_image.employee_id.name}): {e}",
                        "path": __name__,
                        "func": "action_recalculate_all_face_encodings",
                        "line": 0,
                    })

                error_count += 1

        # Return notification with results
        message = f"Face encoding recalculation completed. Processed: {processed_count}, Errors: {error_count}"
        notification_type = 'success' if error_count == 0 else 'warning'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Face Encoding Recalculation',
                'message': message,
                'type': notification_type,
                'sticky': False,
            }
        }

    def action_encode_tracking_images(self):
        """Generate face encodings for tracking images that don't have them yet"""
        # Get all tracking images without face encodings
        tracking_images = self.search([
            ("image", "!=", False),
            ("face_encoding", "=", False)
        ])

        if not tracking_images:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Images Found',
                    'message': 'No tracking images without face encodings found.',
                    'type': 'info',
                    'sticky': False,
                }
            }

        processed_count = 0
        error_count = 0

        for record in tracking_images:
            try:
                # Process tracking image directly
                img = Image.open(BytesIO(base64.b64decode(record.image))).convert("RGB")

                # Use face detection with better sensitivity for tracking images
                face_locations = face_recognition.face_locations(np.array(img), model="hog", number_of_times_to_upsample=1)
                tracking_encodings = face_recognition.face_encodings(np.array(img), face_locations)

                if tracking_encodings and len(tracking_encodings) == 1:
                    # Store the face encoding
                    record.face_encoding = json.dumps(tracking_encodings[0].tolist())
                    processed_count += 1

                    self.env["ir.logging"].create({
                        "name": "Face Encoding Success",
                        "type": "server",
                        "message": f"Successfully processed tracking image {record.id} - face encoding generated",
                        "path": __name__,
                        "func": "action_encode_tracking_images",
                        "line": 0,
                    })
                else:
                    error_count += 1
                    if not tracking_encodings:
                        error_msg = f"No face found in tracking image {record.id}"
                    else:
                        error_msg = f"Multiple faces detected in tracking image {record.id} - {len(tracking_encodings)} faces found"

                    self.env["ir.logging"].create({
                        "name": "Face Encoding Warning",
                        "type": "server",
                        "message": error_msg,
                        "path": __name__,
                        "func": "action_encode_tracking_images",
                        "line": 0,
                    })

            except Exception as e:
                error_count += 1
                self.env["ir.logging"].create({
                    "name": "Face Encoding Error",
                    "type": "server",
                    "message": f"Error processing tracking image {record.id}: {e}",
                    "path": __name__,
                    "func": "action_encode_tracking_images",
                    "line": 0,
                })

        # Return notification with results
        message = f"Tracking image face encoding completed. Processed: {processed_count}, Errors: {error_count}"
        notification_type = 'success' if error_count == 0 else 'warning'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Tracking Image Face Encoding',
                'message': message,
                'type': notification_type,
                'sticky': False,
            }
        }

    def action_debug_face_recognition_settings(self):
        """Display current face recognition settings for debugging"""
        settings_info = {
            'Primary Threshold': '40% (restored from working version)',
            'Fallback Distance': '0.7 (restored from working version)',
            'Validation Logic': 'Simplified (no confidence gap requirement)',
            'Multiple Fallback Layers': 'Removed (was causing false negatives)'
        }

        settings_text = '\n'.join([f"{key}: {value}" for key, value in settings_info.items()])

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Face Recognition Settings',
                'message': f"Current settings restored to working version logic:\n{settings_text}",
                'type': 'info',
                'sticky': True,
            }
        }
