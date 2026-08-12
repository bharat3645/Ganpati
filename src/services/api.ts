import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface Logo {
  id: string;
  name: string;
  imageUrl: string;
}

export interface GenerateRequest {
  ganeshImageId: string;
  userPhotoBase64: string;
  selectedLogoId: string;
}

export interface GenerateResponse {
  success: boolean;
  imageUrl: string;
}

class APIService {
  private api = axios.create({
    baseURL: API_BASE_URL,
    timeout: 120000, // 2 minutes for image generation
    headers: {
      'Content-Type': 'application/json',
    },
  });

  constructor() {
    // Add request interceptor for logging
    this.api.interceptors.request.use(
      (config) => {
        console.log(`Making ${config.method?.toUpperCase()} request to ${config.url}`);
        return config;
      },
      (error) => {
        console.error('Request error:', error);
        return Promise.reject(error);
      }
    );

    // Add response interceptor for error handling
    this.api.interceptors.response.use(
      (response) => {
        console.log(`Response received from ${response.config.url}:`, response.status);
        return response;
      },
      (error) => {
        console.error('Response error:', error.response?.data || error.message);
        return Promise.reject(error);
      }
    );
  }

  async getLogos(): Promise<Logo[]> {
    try {
      console.log('Fetching logos from backend...');
      const response = await this.api.get<Logo[]>('/api/logos');
      console.log('Logos fetched successfully:', response.data);
      return response.data;
    } catch (error) {
      console.error('Failed to fetch logos:', error);
      if (axios.isAxiosError(error)) {
        if (error.code === 'ECONNREFUSED') {
          throw new Error('Backend server is not running. Please start the backend server.');
        }
        throw new Error(`Failed to fetch logos: ${error.response?.data?.detail || error.message}`);
      }
      throw new Error('Failed to fetch logos');
    }
  }

  async generateGreeting(request: GenerateRequest): Promise<GenerateResponse> {
    try {
      console.log('Generating greeting with request:', {
        ganeshImageId: request.ganeshImageId,
        selectedLogoId: request.selectedLogoId,
        userPhotoSize: request.userPhotoBase64.length
      });
      
      const response = await this.api.post<GenerateResponse>('/api/generate', request);
      console.log('Greeting generated successfully');
      return response.data;
    } catch (error) {
      console.error('Failed to generate greeting:', error);
      if (axios.isAxiosError(error)) {
        if (error.code === 'ECONNREFUSED') {
          throw new Error('Backend server is not running. Please start the backend server.');
        }
        if (error.response?.status === 400) {
          throw new Error(`Invalid request: ${error.response.data?.detail || 'Bad request'}`);
        }
        if (error.response?.status === 500) {
          throw new Error(`Server error: ${error.response.data?.detail || 'Internal server error'}`);
        }
        throw new Error(`Failed to generate greeting: ${error.response?.data?.detail || error.message}`);
      }
      throw new Error('Failed to generate greeting');
    }
  }

  async healthCheck(): Promise<boolean> {
    try {
      await this.api.get('/health');
      return true;
    } catch (error) {
      console.error('Health check failed:', error);
      return false;
    }
  }
}

export const apiService = new APIService();