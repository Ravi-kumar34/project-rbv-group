const video = document.getElementById('video');
const canvas = document.getElementById('canvas');

async function startCamera(){
    try{
        const stream = await navigator.mediaDevices.getUserMedia({video: true});
        video.srcObject = stream;
    }
    catch(err){
        alert("Camera access denied");
    }
}

function captureImage(){
    const context = canvas.getContext('2d');

    canvas.height = video.videoHeight;
    canvas.width = video.videoWidth;

    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const imageData = canvas.toDataURL('image/jpeg');

    return imageData;
}

async function capture(){
    const imageData = captureImage();

    try{
const response = await fetch("http://10.221.28.246:8000/login" ,{
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({image: imageData})
        });

        const data = await response.json();
        if(data.message === "Login Success"){
            alert("Login successful!");
            // Save the UID in the browser so the lobby can use it
            localStorage.setItem("user_uid", data.uid);
            // Redirect to the new lobby page
            window.location.href = "lobby.html";
        } else {
            alert("Face not recognized");
        }
    }
    catch(err){
        alert("Server error");
    }
}
startCamera();