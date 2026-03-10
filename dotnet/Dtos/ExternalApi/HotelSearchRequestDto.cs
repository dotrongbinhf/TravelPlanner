using System.ComponentModel.DataAnnotations;

namespace dotnet.Dtos.ExternalApi
{
    /// <summary>
    /// Request DTO for Google Hotels API via SerpApi.
    /// API Reference: https://serpapi.com/google-hotels-api
    /// </summary>
    public class HotelSearchRequestDto
    {
        // === Search Query ===

        /// <summary>
        /// Search query. You can use anything that you would use in a regular Google Hotels search.
        /// Example: "Bali Resorts", "Hotels in Paris"
        /// </summary>
        [Required]
        public string? Q { get; set; }

        // === Advanced Parameters ===

        /// <summary>
        /// Check-in date. Format: YYYY-MM-DD (e.g., "2026-03-10")
        /// </summary>
        [Required]
        public string? CheckInDate { get; set; }

        /// <summary>
        /// Check-out date. Format: YYYY-MM-DD (e.g., "2026-03-11")
        /// </summary>
        [Required]
        public string? CheckOutDate { get; set; }

        /// <summary>
        /// Number of adults. Default: 2.
        /// </summary>
        public int Adults { get; set; } = 2;

        /// <summary>
        /// Number of children. Default: 0.
        /// </summary>
        public int Children { get; set; } = 0;

        /// <summary>
        /// Ages of children (1-17). Comma-separated. The count must match Children parameter.
        /// Example for single child: "5". Example for multiple: "5,8,10"
        /// </summary>
        public string? ChildrenAges { get; set; }

        // === Localization ===

        /// <summary>
        /// Country to use for the Google Hotels search. Two-letter country code.
        /// Example: "us" for United States, "uk" for United Kingdom, "fr" for France.
        /// See: https://serpapi.com/google-countries
        /// </summary>
        public string Gl { get; set; } = "us";

        /// <summary>
        /// Language to use for the Google Hotels search. Two-letter language code.
        /// Example: "en" for English, "es" for Spanish, "fr" for French.
        /// See: https://serpapi.com/google-languages
        /// </summary>
        public string Hl { get; set; } = "en";

        /// <summary>
        /// Currency of the returned prices. Default: "USD".
        /// See: https://serpapi.com/google-travel-currencies
        /// </summary>
        public string Currency { get; set; } = "USD";

        // === Advanced Filters ===

        /// <summary>
        /// Sorting order. Default is sort by Relevance.
        /// Options: 3 = Lowest price, 8 = Highest rating, 13 = Most reviewed.
        /// </summary>
        public int? SortBy { get; set; }

        /// <summary>
        /// Lower bound of price range.
        /// </summary>
        public int? MinPrice { get; set; }

        /// <summary>
        /// Upper bound of price range.
        /// </summary>
        public int? MaxPrice { get; set; }

        /// <summary>
        /// Property types to include. Comma-separated IDs.
        /// Example: "17" or "17,12,18".
        /// See: https://serpapi.com/google-hotels-property-types
        /// </summary>
        public string? PropertyTypes { get; set; }

        /// <summary>
        /// Amenities to require. Comma-separated IDs.
        /// Example: "35" or "35,9,19".
        /// See: https://serpapi.com/google-hotels-amenities
        /// </summary>
        public string? Amenities { get; set; }

        /// <summary>
        /// Minimum rating filter.
        /// Options: 7 = 3.5+, 8 = 4.0+, 9 = 4.5+.
        /// </summary>
        public int? Rating { get; set; }

        // === Hotels Filters ===

        /// <summary>
        /// Hotel brands to filter by. Comma-separated IDs from the brands array in the response.
        /// Example: "33" or "33,67,101". Not available for Vacation Rentals.
        /// </summary>
        public string? Brands { get; set; }

        /// <summary>
        /// Hotel star class filter. Comma-separated values.
        /// Options: 2 = 2-star, 3 = 3-star, 4 = 4-star, 5 = 5-star.
        /// Example: "4,5". Not available for Vacation Rentals.
        /// </summary>
        public string? HotelClass { get; set; }

        /// <summary>
        /// Show only results with free cancellation. Not available for Vacation Rentals.
        /// </summary>
        public bool? FreeCancellation { get; set; }

        /// <summary>
        /// Show only results with special offers. Not available for Vacation Rentals.
        /// </summary>
        public bool? SpecialOffers { get; set; }

        /// <summary>
        /// Show only eco-certified results. Not available for Vacation Rentals.
        /// </summary>
        public bool? EcoCertified { get; set; }

        // === Vacation Rentals Filters ===

        /// <summary>
        /// Set to true to search for Vacation Rentals instead of Hotels.
        /// </summary>
        public bool? VacationRentals { get; set; }

        /// <summary>
        /// Minimum number of bedrooms. Default: 0. Only available for Vacation Rentals.
        /// </summary>
        public int? Bedrooms { get; set; }

        /// <summary>
        /// Minimum number of bathrooms. Default: 0. Only available for Vacation Rentals.
        /// </summary>
        public int? Bathrooms { get; set; }
    }
}
