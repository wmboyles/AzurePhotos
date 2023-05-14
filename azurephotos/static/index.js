// imageUrls is passed here from HTML from Flask
$(document).ready(() => {

    const LEFT_ARROW = 37;
    const RIGHT_ARROW = 39;
    const DELETE = 127;

    // let imageUrls = {{ images | tojson}};
    let thumbnails = $(".image-container img");

    const modal = $("#imageModal");
    const fullImage = $("#fullImage");

    // Index of image last displayed in modal
    let index = -1;

    function updateModal(index) {
        const imageUrl = imageUrls[index];
        fullImage.attr("src", "fullsize/" + imageUrl);
        modal.modal("show");
    }

    thumbnails.on("click", function (e) {
        if (modal.is(":visible")) return

        index = $(this).index();
        updateModal(index);
    });

    function prevImage() {
        if (index === 0) return;
        index--;

        updateModal(index)
    }

    function nextImage() {
        if (index === imageUrls.length - 1) return;
        index++;

        updateModal(index);
    }

    function deleteImage() {
        if (!confirm("Are you sure you want to delete?")) return;

        const imageUrl = imageUrls[index];
        fetch(`/delete/${imageUrl}`, { method: "DELETE" })
            .then(response => {
                modal.modal("hide")
                thumbnails[index].remove()
                imageUrls.splice(index, 1)
                thumbnails.splice(index, 1)
                index = -1
            })
            .catch(error => {
                console.log(error);
            });
    }

    $("#prevBtn").click(prevImage);

    $("#nextBtn").click(nextImage);

    $("#deleteBtn").click(deleteImage);

    modal.on("keydown", function (e) {
        if (!modal.is(":visible")) return;

        if (e.keyCode === LEFT_ARROW) {
            prevImage();
        } else if (e.keyCode === RIGHT_ARROW) {
            nextImage();
        } else if (e.keyCode === DELETE) {
            deleteImage()
        }
    });
});