export class TokenStorage {
  static setAccessToken(token: string): void {
    try {
      localStorage.setItem("accessToken", token);
    } catch (error) {
      console.error("Failed to store access token:", error);
    }
  }

  static getAccessToken(): string | null {
    try {
      return localStorage.getItem("accessToken");
    } catch (error) {
      console.error("Failed to get access token:", error);
      return null;
    }
  }

  static removeAccessToken(): void {
    try {
      localStorage.removeItem("accessToken");
    } catch (error) {
      console.error("Failed to remove access token:", error);
    }
  }
}
