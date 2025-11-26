function simulateCameraClick() {
    const cameraButton = document.querySelector(".camera");
    if (cameraButton) {
        cameraButton.click();
        console.log("Camera button clicked!");
    } else {
        console.error("Camera button not found");
    }
}
