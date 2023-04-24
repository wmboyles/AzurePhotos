from flask import Flask, render_template, Response
from PIL import Image
import os
from io import BytesIO

# TODO: How to handle multiple requests in parallel using async/await?
app = Flask(__name__)

# Define a cache to store the resized images
cache: dict[str, BytesIO] = {}


@app.route("/resized/<filename>")
def resized_image(filename, width=200):
    # Serve a resized image from the cache
    images_folder = os.path.join(app.static_folder, "images")
    filepath = os.path.join(images_folder, filename)

    if filepath not in cache:
        buffer = BytesIO()
        with Image.open(filepath) as img:
            img.thumbnail((width, width))

            img.save(buffer, "JPEG")

        cache[filepath] = buffer

    return Response(cache[filepath].getvalue(), mimetype='image/jpeg')


@app.route("/")
def image_display():
    # Get the list of images in the 'static/images' folder
    images_folder = os.path.join(app.static_folder, "images")
    images = os.listdir(images_folder)

    # Render the 'image_display.html' template and pass in the list of images
    return render_template("image_display.html", images=images)


if __name__ == "__main__":
    app.run(debug=True)
