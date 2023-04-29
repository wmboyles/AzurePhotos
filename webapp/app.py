import os
from functools import cache
from io import BytesIO

from flask import Flask, Response, render_template, request, redirect
from PIL import Image
from werkzeug.utils import secure_filename

# TODO: How to handle multiple requests in parallel using async/await?
app = Flask(__name__)
images_folder = os.path.join(app.static_folder, "images")  # type: ignore
delete_folder = os.path.join(app.static_folder, "deleted")  # type: ignore


# TODO: How could we implement caching for clients, sending a 304 if the client already requested an image? This already heppens for /static/images
@app.route("/resized/<filename>")
@cache
def resized_image(filename: str):
    # Serve a resized image from the cache
    filepath = os.path.join(images_folder, filename)

    extension = filename.split(".")[-1]
    if extension == "jpg":
        extension = "jpeg"

    buffer = BytesIO()
    with Image.open(filepath) as img:
        img.thumbnail((370, 280))
        img.save(buffer, extension)

    return Response(buffer.getvalue(), mimetype=f"image/{extension}")


@app.route("/upload", methods=["POST"])
def upload():
    files = request.files.getlist("upload")
    for file in files:
        print(file)

        # TODO: Add image alphabetially earlier than all other images to it appears at the top
        save_filename = secure_filename(str(file.filename))
        file.save(os.path.join(images_folder, save_filename))

    return redirect("/")
    # return Response(status=200)


@app.route("/delete/<filename>", methods=["DELETE"])
def delete(filename: str):
    source = os.path.join(images_folder, filename)

    if not os.path.exists(source):
        return Response(status=404)

    dest = os.path.join(delete_folder, filename)
    os.replace(source, dest)

    return Response(status=204)


@app.route("/")
def image_display():
    # Get the list of images in the 'static/images' folder
    images = os.listdir(images_folder)

    # Render the 'image_display.html' template and pass in the list of images
    return render_template("image_display.html", images=images)


if __name__ == "__main__":
    app.run(debug=True)
