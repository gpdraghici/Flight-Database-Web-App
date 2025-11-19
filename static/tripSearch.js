document.addEventListener("DOMContentLoaded", function(){
    const oneWay = document.getElementById("one-way");
    const roundTrip = document.getElementById("round-trip");
    const returnDate = document.getElementById("returnDate");
    
    oneWay.addEventListener("change", function(){
        if(oneWay.checked){
            returnDate.style.display="none";
        }
    });
    roundTrip.addEventListener("change", function(){
        if(roundTrip.checked){
            returnDate.style.display="block";
        }
    });

});