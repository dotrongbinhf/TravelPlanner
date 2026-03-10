using System.Text.Json.Serialization;

namespace dotnet.Dtos.ExternalApi
{
    /// <summary>
    /// Response DTO for Google Hotels API via SerpApi.
    /// API Reference: https://serpapi.com/google-hotels-api
    /// </summary>
    public class HotelSearchResponseDto
    {
        public HotelSearchInformationDto? SearchInformation { get; set; }
        public List<HotelBrandDto>? Brands { get; set; }
        public List<HotelPropertyDto>? Properties { get; set; }
        public HotelPaginationDto? SerpapiPagination { get; set; }

        /// <summary>
        /// Error message set by the service when the external API call fails. Not part of SerpApi response.
        /// </summary>
        [JsonIgnore]
        public string? Error { get; set; }
    }

    // ========================
    // Search Information
    // ========================

    public class HotelSearchInformationDto
    {
        public int? TotalResults { get; set; }
    }

    // ========================
    // Brands
    // ========================

    public class HotelBrandDto
    {
        public int Id { get; set; }
        public string? Name { get; set; }
        public List<HotelBrandDto>? Children { get; set; }
    }

    // ========================
    // Hotel Property
    // ========================

    public class HotelPropertyDto
    {
        /// <summary>Type of property: "hotel" or "vacation rental"</summary>
        public string? Type { get; set; }

        /// <summary>Name of the property</summary>
        public string? Name { get; set; }

        /// <summary>Description of the property</summary>
        public string? Description { get; set; }

        /// <summary>URL of the property's website</summary>
        public string? Link { get; set; }

        /// <summary>URL of the property's logo</summary>
        public string? Logo { get; set; }

        /// <summary>Indicates if the property result is sponsored</summary>
        public bool? Sponsored { get; set; }

        /// <summary>Indicates if the property is eco-certified</summary>
        public bool? EcoCertified { get; set; }

        /// <summary>GPS coordinates of the property</summary>
        public HotelGpsCoordinatesDto? GpsCoordinates { get; set; }

        /// <summary>Check-in time (e.g., "3:00 PM")</summary>
        public string? CheckInTime { get; set; }

        /// <summary>Check-out time (e.g., "12:00 PM")</summary>
        public string? CheckOutTime { get; set; }

        /// <summary>Rate per night with lowest and before-tax prices</summary>
        public HotelRateDto? RatePerNight { get; set; }

        /// <summary>Total rate for the entire stay</summary>
        public HotelRateDto? TotalRate { get; set; }

        /// <summary>Prices from different booking sources</summary>
        public List<HotelPriceSourceDto>? Prices { get; set; }

        /// <summary>Nearby places with transportation info</summary>
        public List<HotelNearbyPlaceDto>? NearbyPlaces { get; set; }

        /// <summary>Hotel class description (e.g., "5-star hotel")</summary>
        public string? HotelClass { get; set; }

        /// <summary>Extracted hotel class as integer (e.g., 5)</summary>
        public int? ExtractedHotelClass { get; set; }

        /// <summary>Property images</summary>
        public List<HotelImageDto>? Images { get; set; }

        /// <summary>Overall rating of the property</summary>
        public double? OverallRating { get; set; }

        /// <summary>Total number of reviews</summary>
        public int? Reviews { get; set; }

        /// <summary>Rating distribution by stars</summary>
        public List<HotelStarRatingDto>? Ratings { get; set; }

        /// <summary>Location rating (e.g., 1.8 = Bad, 4.8 = Excellent)</summary>
        public double? LocationRating { get; set; }

        /// <summary>Reviews breakdown by category (Service, Property, Nature, etc.)</summary>
        public List<HotelReviewBreakdownDto>? ReviewsBreakdown { get; set; }

        /// <summary>Amenities provided (e.g., "Free Wi-Fi", "Free parking", "Pool")</summary>
        public List<string>? Amenities { get; set; }

        /// <summary>Excluded amenities (e.g., "No air conditioning", "Not pet-friendly")</summary>
        public List<string>? ExcludedAmenities { get; set; }

        /// <summary>Health and safety information</summary>
        public HotelHealthAndSafetyDto? HealthAndSafety { get; set; }

        /// <summary>Essential info for vacation rentals (e.g., "Entire villa", "Sleeps 10", "9 bedrooms")</summary>
        public List<string>? EssentialInfo { get; set; }

        /// <summary>Deal text (e.g., "26% less than usual")</summary>
        public string? Deal { get; set; }

        /// <summary>Deal description (e.g., "Great Deal")</summary>
        public string? DealDescription { get; set; }

        /// <summary>Token to retrieve property details</summary>
        public string? PropertyToken { get; set; }

        /// <summary>SerpApi endpoint for retrieving property details</summary>
        public string? SerpapiPropertyDetailsLink { get; set; }

        /// <summary>SerpApi endpoint for retrieving property reviews</summary>
        public string? SerpapiGoogleHotelsReviewsLink { get; set; }
    }

    // ========================
    // GPS Coordinates
    // ========================

    public class HotelGpsCoordinatesDto
    {
        public double Latitude { get; set; }
        public double Longitude { get; set; }
    }

    // ========================
    // Rate (used for rate_per_night and total_rate)
    // ========================

    public class HotelRateDto
    {
        /// <summary>Lowest rate formatted with currency (e.g., "$111")</summary>
        public string? Lowest { get; set; }

        /// <summary>Extracted numeric lowest rate (e.g., 111)</summary>
        public double? ExtractedLowest { get; set; }

        /// <summary>Rate before taxes and fees formatted with currency (e.g., "$93")</summary>
        public string? BeforeTaxesFees { get; set; }

        /// <summary>Extracted numeric rate before taxes and fees (e.g., 93)</summary>
        public double? ExtractedBeforeTaxesFees { get; set; }
    }

    // ========================
    // Price Source (booking providers)
    // ========================

    public class HotelPriceSourceDto
    {
        /// <summary>Name of the booking source</summary>
        public string? Source { get; set; }

        /// <summary>Logo URL of the booking source</summary>
        public string? Logo { get; set; }

        /// <summary>Number of guests this price applies to</summary>
        public int? NumGuests { get; set; }

        /// <summary>Rate per night from this source</summary>
        public HotelRateDto? RatePerNight { get; set; }

        /// <summary>Whether free cancellation is available from this source</summary>
        public bool? FreeCancellation { get; set; }

        /// <summary>Free cancellation deadline date (e.g., "Mar 17")</summary>
        public string? FreeCancellationUntilDate { get; set; }

        /// <summary>Free cancellation deadline time (e.g., "3:59 PM")</summary>
        public string? FreeCancellationUntilTime { get; set; }
    }

    // ========================
    // Nearby Place
    // ========================

    public class HotelNearbyPlaceDto
    {
        /// <summary>Name of the nearby place</summary>
        public string? Name { get; set; }

        /// <summary>Available transportation options to/from this place</summary>
        public List<HotelTransportationDto>? Transportations { get; set; }
    }

    public class HotelTransportationDto
    {
        /// <summary>Type of transportation (e.g., "Taxi", "Walking", "Public transport")</summary>
        public string? Type { get; set; }

        /// <summary>Travel duration (e.g., "30 min", "1 hr 15 min")</summary>
        public string? Duration { get; set; }
    }

    // ========================
    // Image
    // ========================

    public class HotelImageDto
    {
        /// <summary>URL of the thumbnail image</summary>
        public string? Thumbnail { get; set; }

        /// <summary>URL of the original full-size image</summary>
        public string? OriginalImage { get; set; }
    }

    // ========================
    // Star Rating Distribution
    // ========================

    public class HotelStarRatingDto
    {
        /// <summary>Number of stars (1 to 5)</summary>
        public int Stars { get; set; }

        /// <summary>Total number of reviews for this star rating</summary>
        public int Count { get; set; }
    }

    // ========================
    // Review Breakdown
    // ========================

    public class HotelReviewBreakdownDto
    {
        /// <summary>Category name (e.g., "Service", "Property", "Nature")</summary>
        public string? Name { get; set; }

        /// <summary>Description of the category</summary>
        public string? Description { get; set; }

        /// <summary>Total mentions of this category</summary>
        public int? TotalMentioned { get; set; }

        /// <summary>Number of positive mentions</summary>
        public int? Positive { get; set; }

        /// <summary>Number of negative mentions</summary>
        public int? Negative { get; set; }

        /// <summary>Number of neutral mentions</summary>
        public int? Neutral { get; set; }
    }

    // ========================
    // Health and Safety
    // ========================

    public class HotelHealthAndSafetyDto
    {
        public List<HotelHealthAndSafetyGroupDto>? Groups { get; set; }
    }

    public class HotelHealthAndSafetyGroupDto
    {
        /// <summary>Name of the amenity group (e.g., "Enhanced cleaning", "Minimized contact")</summary>
        public string? Title { get; set; }

        /// <summary>List of health/safety amenities in this group</summary>
        public List<HotelHealthAndSafetyItemDto>? List { get; set; }
    }

    public class HotelHealthAndSafetyItemDto
    {
        /// <summary>Name of the amenity</summary>
        public string? Title { get; set; }

        /// <summary>Whether the amenity is available</summary>
        public bool Available { get; set; }
    }

    // ========================
    // Pagination
    // ========================

    public class HotelPaginationDto
    {
        public int? CurrentFrom { get; set; }
        public int? CurrentTo { get; set; }
        public string? NextPageToken { get; set; }
        public string? Next { get; set; }
    }
}
