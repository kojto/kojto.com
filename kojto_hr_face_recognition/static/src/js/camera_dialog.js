/** @odoo-module */

import { Dialog } from "@web/core/dialog/dialog";
const { useRef, onMounted, useState, Component, onWillUnmount } = owl;
/**
 * creating a dialogue to show camera
 */
export class CameraDialog extends Component {
    setup() {
        super.setup();
        this.video = useRef("video");
        this.image = useRef("image");
        this.state = useState({
            img: false,
        });
        onMounted(async () => {
            this.video.el.srcObject = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        });
        onWillUnmount(() => {
            this.stopCamera();
        });
    }
    /**
     * Closes the camera
     */
    _cancel() {
        this.env.dialogData.close();
        this.stopCamera();
    }
    /**
     * Saves the Image
     */
    _confirm() {
        let video = this.video.el;
        let image = this.image.el;
        const canvas = document.createElement("canvas");
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const canvasContext = canvas.getContext("2d");
        canvasContext.drawImage(video, 0, 0);
        this.state.img = canvas.toDataURL("image/jpeg");
        this.img_binary = this.state.img.split(",")[1];
        video.classList.add("d-none");
        image.classList.remove("d-none");
        image.src = this.state.img;
    }
    /**
     * Updates the image
     */
    async _save() {
        // Create a new record with the image instead of updating a draft record
        const result = await this.env.services.orm.create(
            'kojto.hr.face.recognition',
            [{ image: this.img_binary }]
        );

        this.env.dialogData.close();
        this.stopCamera();

        // Reopen the terminal to show the newly created record with success/error message
        if (result) {
            await this.env.services.action.doAction('kojto_hr_face_recognition.action_kojto_hr_terminal_server');
        }
    }
    /**
     * Resets the Image
     */
    _reset() {
        this.img_binary = false;
        this.state.img = false;
        this.video.el.classList.remove("d-none");
        this.image.el.classList.add("d-none");
    }
    /**
     * Closes camera
     */
    _close() {
        this.stopCamera();
    }
    /**
     * Stop camera
     */
    stopCamera() {
        this.video.el.srcObject.getVideoTracks().forEach((track) => {
            track.stop();
        });
    }
}
CameraDialog.template = "kojto_hr_face_recognition.camera_dialog";
CameraDialog.components = { Dialog };
