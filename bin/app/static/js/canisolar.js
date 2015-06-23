function geocode() {
	geocoder = new google.maps.Geocoder();
	geocoder.geocode({ 'address': document.getElementById("address").value}, 
		function(results, status) {
		  if (status == google.maps.GeocoderStatus.OK) {
			var state = '';
			var state_name = '';
			var zipcode = '';
			var locality = '';
			var arrayLength = results[0].address_components.length;
			for (var i = 0; i < arrayLength; i++) {
				if (results[0].address_components[i].types.indexOf('administrative_area_level_1') > -1) {
					state = results[0].address_components[i].short_name;
					state_name = results[0].address_components[i].long_name;
				}
				if (results[0].address_components[i].types.indexOf('postal_code') > -1)  {
					zipcode = results[0].address_components[i].short_name;
				}						
				if (results[0].address_components[i].types.indexOf('locality') > -1)  {
					locality = results[0].address_components[i].short_name;
				}
				if (locality === '') {
					if (results[0].address_components[i].types.indexOf('administrative_area_level_2') > -1)  {
						locality = results[0].address_components[i].short_name;
					}
				}						
			}
			document.getElementById("lat").value = results[0].geometry.location.lat();
			document.getElementById("lng").value = results[0].geometry.location.lng();
			document.getElementById("state").value = state;
			document.getElementById("state_name").value = state_name;
			document.getElementById("locality").value = locality;
			document.getElementById("zipcode").value = zipcode;
			document.myform.action = "/output";
			document.myform.submit();	
		  } else {
		  // Write some error handling code here
			document.getElementById("subtitle").innerHTML = "Sorry, I couldn't find that location."				
		  }
		}
	);
}

function slider1_input(val) {
	var el = document.getElementById("slider1_span");
	val = Math.floor(val * 100);
	val = val.toString();
	val = val.concat('%')				
	el.innerHTML = val;
}

// Since JS indices run 0 to 11, we don't subtract one to get the previous month. But we do change 0 to 12.
function getMonthVal() {
	var d = new Date();
	var n = d.getMonth();
	if (n === 0) {
		n = 12;
	}
	return n;
}