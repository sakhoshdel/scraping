
function sendRequest() {
    $(document).ready(function () {
      $("#search").keyup(function () {
        // Get search parameters from user input or other elements
        // var model = $("#search").val();
        var brand = $("#brandInput").val();
        var ram = $("#ramInput").val();
        var memory = $("#memoryInput").val();
        var color = $("#colorInput").val();
        var color = $("#vietnamInput").val();

        var url =
          "http://127.0.0.1:8000/search/?model=" +
          model +
          "&brand=" +
          brand +
          "&ram=" +
          ram +
          "&memory=" +
          memory +
          "&color=" +
          color;

        // Make an AJAX request to the Django backend
        $.ajax({
          url: url,
          method: "GET",
          data: {
            model: model,
            brand: brand,
            ram: ram,
            memory: memory,
            color: color,
          },
          success: function (response) {
            // Handle the response from Django
            console.log(response);
            // Update your frontend with the received data
          },
          error: function (xhr, status, error) {
            // Handle any errors
            console.error(xhr.responseText);
          },
        });
      });
    });
    console.log()
  }