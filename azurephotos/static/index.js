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
        fullImage.attr("src", "/fullsize/" + imageUrl);
        modal.modal("show");
    }

    thumbnails.on("click", function (e) {
        if (modal.is(":visible")) return;

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
        const isAlbum = typeof (album) !== "undefined";
        if (!confirm(isAlbum ?
            "Are you sure you want to remove from this album?" :
            "Are you sure you want to delete?")) {
            return
        }

        const imageUrl = imageUrls[index];
        const deleteUrl = isAlbum ? `/api/albums/${album}/${imageUrl}` : `/delete/${imageUrl}`

        fetch(deleteUrl, { method: "DELETE" })
            .then(_ => {
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

    function createAlbum() {
        const albumName = prompt("Enter album name");
        fetch(`/api/albums/${albumName}`, { method: "POST" })
            .then(response => {
                albums.push(albumName);
                window.location.reload();
            }).catch(error => {
                console.log(error);
            });
    }

    function deleteAlbum() {
        alert("Are you sure you want to delete this album?");
        fetch(`/api/albums/${album}`, { method: "DELETE" })
            .then(response => {
                window.location.href = "/";
            }).catch(error => {
                console.log(error);
            });
    }

    function renameAlbum() {
        const newAlbumName = prompt("Enter new album name");
        fetch(`/api/albums/${album}/rename/${newAlbumName}`, { method: "PUT" })
            .then(response => {
                album = newAlbumName;
                window.location.href = `/albums/${newAlbumName}`;
            }).catch(error => {
                console.log(error);
            });
    }

    function addToAlbum(album) {
        const imageUrl = imageUrls[index];
        fetch(`/api/albums/${album}/${imageUrl}`, { method: "POST" })
            .then(response => {
            })
            .catch(error => {
                console.log(error)
            });
    }

    $("#prevBtn").click(prevImage);

    $("#nextBtn").click(nextImage);

    $("#deleteBtn").click(deleteImage);

    $("#createAlbumBtn").click(createAlbum);

    $("#deleteAlbumBtn").click(deleteAlbum);

    $("#renameAlbumBtn").click(renameAlbum);

    $("#addToAlbumBtn").siblings("ul").find("li .dropdown-item").each(function () {
        var button = $(this);
        const albumName = button.text();
        button.click(() => addToAlbum(albumName))
        // button.attr("onclick", addToAlbum(albumName))
    });

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