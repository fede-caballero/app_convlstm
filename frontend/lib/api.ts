export interface ApiStatus {
  status: string;
  files_in_buffer?: number;
  files_needed_for_run?: number;
  last_update?: string;
}

// Interface for a detected storm cell
export interface StormCell {
  lat: number;
  lon: number;
  max_dbz: number;
  type: string;
}

// Nueva interfaz para una imagen con sus coordenadas
export interface ImageWithBounds {
  url: string;
  bounds: [[number, number], [number, number]];
  target_time?: string;
  cells?: StormCell[];
}

// Actualizamos la interfaz principal de imágenes
export interface ApiImages {
  input_images: ImageWithBounds[];
  prediction_images: ImageWithBounds[];
}

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

// MOCK DATA FOR LOCAL TESTING
// We will load this from metadata.json if the API fails
let MOCK_DATA_CACHE: ImageWithBounds[] | null = null;

async function getMockData(): Promise<ImageWithBounds[]> {
  if (MOCK_DATA_CACHE) return MOCK_DATA_CACHE;
  try {
    const res = await fetch('/mock_data/metadata.json');
    if (res.ok) {
      MOCK_DATA_CACHE = await res.json();
      return MOCK_DATA_CACHE || [];
    }
  } catch (e) {
    console.error("Failed to load mock metadata", e);
  }
  return [];
}

const MOCK_STATUS: ApiStatus = {
  status: "OFFLINE",
  files_in_buffer: 0,
  files_needed_for_run: 8,
  last_update: undefined
};

async function fetchApi<T>(endpoint: string): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  try {
    const response = await fetch(url, { cache: 'no-store' });
    if (!response.ok) {
      throw new Error(`API request failed with status ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.warn(`Failed to fetch from ${url}, falling back to mock data.`);

    if (endpoint === '/api/status') return MOCK_STATUS as unknown as T;

    if (endpoint === '/api/images') {
      const images = await getMockData();
      // Split images for demo: first 10 as input, last 5 as prediction
      const splitIndex = Math.max(0, images.length - 5);
      const bufferSize = MOCK_STATUS?.files_in_buffer ?? 0
      const bufferMaxSize = MOCK_STATUS?.files_needed_for_run ?? 8
      const lastPredictionTime = MOCK_STATUS?.last_update
        ? new Date(MOCK_STATUS.last_update).toLocaleTimeString()
        : "--:--"
      return {
        input_images: images.slice(0, splitIndex),
        prediction_images: images.slice(splitIndex)
      } as unknown as T;
    }
    throw error;
  }
}

export const fetchStatus = (): Promise<ApiStatus> => fetchApi<ApiStatus>('/api/status');

// La función fetchImages ahora maneja la nueva estructura
export const fetchImages = async (): Promise<ApiImages> => {
  const data = await fetchApi<ApiImages>('/api/images');

  // Si estamos en modo mock (data ya tiene URLs relativas válidas), retornamos directo
  if ((data as any).input_images?.[0]?.url.startsWith('/')) {
    return data;
  }

  // Mapeamos sobre los arrays para construir las URLs absolutas si vienen del backend
  const processImages = (images: ImageWithBounds[]) => {
    if (!Array.isArray(images)) return [];
    return images.map(image => ({
      ...image,
      // Si la URL ya es absoluta o relativa, la dejamos. Si no, asumimos que es relativa a la raíz.
      url: image.url.startsWith('http') || image.url.startsWith('/') ? image.url : `/${image.url}`
    }));
  };

  return {
    input_images: processImages(data.input_images),
    prediction_images: processImages(data.prediction_images),
  };
};

// --- Reporting API ---

export interface WeatherReport {
  id?: number;
  report_type: string;
  latitude: number;
  longitude: number;
  timestamp?: string; // ISO
  description?: string;
  username?: string; // enriched by backend
}

export const submitReport = async (report: WeatherReport, token: string): Promise<void> => {
  const res = await fetch(`${API_BASE_URL}/api/reports`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify(report)
  });
  if (!res.ok) throw new Error("Failed to submit report");
};

export const fetchReports = async (hours: number = 24): Promise<WeatherReport[]> => {
  try {
    const res = await fetch(`${API_BASE_URL}/api/reports?hours=${hours}`, { cache: 'no-store' }); // Ensure fresh data
    if (!res.ok) throw new Error("Failed to fetch reports");
    return await res.json();
  } catch (e) {
    console.error(e);
    return [];
  }
};
