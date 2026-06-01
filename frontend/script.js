const video = document.getElementById("video");
const canvas = document.getElementById("canvas");

// ---------------- CAMERA ----------------
async function startCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: true
        });

        video.srcObject = stream;
    }
    catch (err) {
        console.error(err);
        alert("Camera access denied");
    }
}

// ---------------- CAPTURE IMAGE ----------------
function captureImage() {

    if (!video.videoWidth || !video.videoHeight) {
        alert("Camera not ready yet");
        return null;
    }

    const context = canvas.getContext("2d");

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    context.drawImage(
        video,
        0,
        0,
        canvas.width,
        canvas.height
    );

    return canvas.toDataURL("image/jpeg");
}

// ---------------- FACE LOGIN ----------------
async function capture() {

    const imageData = captureImage();

    if (!imageData) return;

    const host = window.location.hostname;

    try {

        const response = await fetch(
            `http://${host}:8000/login`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    image: imageData
                })
            }
        );

        const data = await response.json();

        if (data.message === "Login Success") {

            localStorage.setItem("user_uid", data.uid);

            alert("Login Successful");

            window.location.href = "lobby.html";
        }
        else {
            alert(data.message || "Face not recognized");
        }

    }
    catch (err) {
        console.error(err);
        alert("Server error");
    }
}

// ---------------- ROLL NO LOGIN ----------------
async function loginWithRollNo() {

    const rollNo = document
        .getElementById("rollNo")
        .value
        .trim();

    if (!rollNo) {
        alert("Please enter a Roll Number");
        return;
    }

    const host = window.location.hostname;

    try {

        const response = await fetch(
            `http://${host}:8000/loginroll?dev_uid=${encodeURIComponent(rollNo)}`,
            {
                method: "POST"
            }
        );

        const data = await response.json();

        if (data.message === "Login Success") {

            localStorage.setItem("user_uid", data.uid);

            alert("Login Successful");

            window.location.href = "lobby.html";
        }
        else {
            alert(data.message || "Invalid Roll Number");
        }

    }
    catch (err) {
        console.error(err);
        alert("Server error");
    }
}

// ---------------- START CAMERA ON PAGE LOAD ----------------
startCamera();