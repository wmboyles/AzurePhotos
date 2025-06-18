// imageUrls is passed here from HTML from Flask
$(document).ready(() => {
    // let imageUrls = {{ images | tojson}};
    // let thumbnails = $(".image-container img");

    // const modal = $("#imageModal");
    // const fullImage = $("#fullImage");

    // Index of image last displayed in modal
    // let index = -1;

    const modalImage = document.getElementById('modalImage');
    const imageModal = document.getElementById('imageModal');

    // Open model on click
    imageModal.addEventListener('show.bs.modal', function (event) {
        const trigger = event.relatedTarget;
        const fullSrc = trigger.getAttribute('data-full');
        modalImage.src = fullSrc;
    });

    // TODO: Reimplement
    // function deleteImage() {
    //     const isAlbum = typeof (album) !== "undefined";
    //     if (!confirm(isAlbum ?
    //         "Are you sure you want to remove from this album?" :
    //         "Are you sure you want to delete?")) {
    //         return
    //     }

    //     const imageUrl = imageUrls[index];
    //     const deleteUrl = isAlbum ? `/api/albums/${album}/${imageUrl}` : `/delete/${imageUrl}`

    //     fetch(deleteUrl, { method: "DELETE" })
    //         .then(_ => {
    //             modal.modal("hide")
    //             thumbnails[index].remove()
    //             imageUrls.splice(index, 1)
    //             thumbnails.splice(index, 1)
    //             index = -1
    //         })
    //         .catch(error => {
    //             console.log(error);
    //         });
    // }

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

    // TODO: Reimplement
    // function addToAlbum(album) {
    //     const imageUrl = imageUrls[index];
    //     fetch(`/api/albums/${album}/${imageUrl}`, { method: "POST" })
    //         .then(_ => {
    //             modal.modal("hide")
    //             thumbnails[index].remove()
    //             imageUrls.splice(index, 1)
    //             thumbnails.splice(index, 1)
    //             index = -1
    //         })
    //         .catch(error => {
    //             console.log(error)
    //         });
    // }

    // $("#deleteBtn").click(deleteImage);

    $("#createAlbumBtn").click(createAlbum);

    $("#deleteAlbumBtn").click(deleteAlbum);

    $("#renameAlbumBtn").click(renameAlbum);

    // $("#addToAlbumBtn").siblings("ul").find("li .dropdown-item").each(function () {
    //     var button = $(this);
    //     const albumName = button.text();
    //     button.click(() => addToAlbum(albumName))
    //     // button.attr("onclick", addToAlbum(albumName))
    // });
});