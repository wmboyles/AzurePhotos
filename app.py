from flask import Flask, render_template, Response
from PIL import Image
import os
from io import BytesIO
from functools import cache

# TODO: How to handle multiple requests in parallel using async/await?
app = Flask(__name__)

# TODO: How could we implement caching for clients, sending a 304 if the client already requested an image? This already heppens for /static/images
@app.route("/resized/<filename>")
@cache
def resized_image(filename, width=300):
    # Serve a resized image from the cache
    images_folder = os.path.join(app.static_folder, "images")
    filepath = os.path.join(images_folder, filename)

    buffer = BytesIO()
    with Image.open(filepath) as img:
        img.thumbnail((width, width))
        img.save(buffer, "JPEG")

    return Response(buffer.getvalue(), mimetype='image/jpeg')


@app.route("/")
def image_display():
    # Get the list of images in the 'static/images' folder
    images_folder = os.path.join(app.static_folder, "images")
    images = os.listdir(images_folder)

    # Render the 'image_display.html' template and pass in the list of images
    return render_template("image_display.html", images=images)


if __name__ == "__main__":
    app.run(debug=True)
