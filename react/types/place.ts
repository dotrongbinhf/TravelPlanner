export type GeoJson = {
  type: string;
  coordinates: [number, number]; // long, lati
};

export type OpenHours = {
  monday: string[];
  tuesday: string[];
  wednesday: string[];
  thursday: string[];
  friday: string[];
  saturday: string[];
  sunday: string[];
};

export type PlaceImage = {
  title: string;
  image: string;
};

export type UserReview = {
  name: string;
  profilePicture: string;
  rating: number;
  description: string;
  images: string[];
  when: string;
};

export type ReviewsPerRating = Record<string, number>;

export type Place = {
  id: string; // MongoDB ObjectId
  placeId: string; // Google Place ID
  link: string;
  title: string;
  category: string;
  location: GeoJson;
  address: string;
  openHours: OpenHours;
  website: string;
  reviewCount: number;
  reviewRating: number;
  reviewsPerRating: ReviewsPerRating;
  cid: string;
  description: string;
  thumbnail: string;
  images: PlaceImage[];
  userReviews: UserReview[];
  createdDate: string;
  modifiedDate: string;
};
