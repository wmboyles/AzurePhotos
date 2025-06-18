// imageUrls is passed here from HTML from Flask
// We'll also have albums on the main page and album on an album page
$(document).ready(() => {
    // Last viewed photo in modal
    let modalPhotoName = null;

    // Modal for viewing images
    const imageModal = document.getElementById('imageModal');

    // Open modal when clicking on a thumbnail
    imageModal.addEventListener('show.bs.modal', function (event) {
        const trigger = event.relatedTarget;
        const fullSrc = trigger.getAttribute('data-full');

        document.getElementById('modalImage').src = fullSrc;
        modalPhotoName = fullSrc.slice("/fullsize/".length);
    });

    function deleteImage() {
        const isAlbum = typeof (album) !== "undefined";
        if (!confirm(isAlbum ?
            "Are you sure you want to remove from this album?" :
            "Are you sure you want to delete?")) {
            return
        }

        // TODO: Need to test deleting from album
        const deleteUrl = isAlbum ? `/api/albums/${album}/${modalPhotoName}` : `/delete/${modalPhotoName}`

        fetch(deleteUrl, { method: "DELETE" })
            .then(response => {
                if(response.ok)
                {
                    const deletedThumbnail = document.querySelector(`[data-full="/fullsize/${modalPhotoName}"]`)
                    if (deletedThumbnail) {
                        deletedThumbnail.closest(".col").remove();
                    }
                    bootstrap.Modal.getInstance(imageModal).hide();
                    modalPhotoName = null;
                } else {
                    alert(response);
                }
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

    $("#deleteBtn").click(deleteImage);

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