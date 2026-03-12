package net.famzangl.minecraft.minebot.ai.cambiumInputs;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

import net.famzangl.minecraft.minebot.ai.command.AIChatController;

/**
 * Utility class for making HTTP requests to the backend API
 */
public class APIClient {
    private static final String BASE_URL = System.getProperty("cambium.api.url", "http://backend:8000");
    
    /**
     * Makes a POST request to the API
     * @param endpoint The API endpoint (e.g., "/predict-action/v1")
     * @param jsonPayload The JSON payload to send
     * @return The response as a string, or null on error
     */
    private static final int CONNECT_TIMEOUT_MS = 3000;
    private static final int READ_TIMEOUT_MS = 5000;
    private static final int MAX_RETRIES = 2;
    
    public static String postRequest(String endpoint, String jsonPayload) {
        String urlString = BASE_URL + endpoint;
        Exception lastException = null;
        
        for (int attempt = 0; attempt < MAX_RETRIES; attempt++) {
            HttpURLConnection conn = null;
            try {
                URL url = new URL(urlString);
                conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("POST");
                conn.setRequestProperty("Content-Type", "application/json");
                conn.setDoOutput(true);
                conn.setConnectTimeout(CONNECT_TIMEOUT_MS);
                conn.setReadTimeout(READ_TIMEOUT_MS);
                
                if (jsonPayload != null) {
                    OutputStream os = conn.getOutputStream();
                    os.write(jsonPayload.getBytes(StandardCharsets.UTF_8));
                    os.close();
                }
                
                int responseCode = conn.getResponseCode();
                InputStream is = responseCode == HttpURLConnection.HTTP_OK
                        ? conn.getInputStream()
                        : conn.getErrorStream();
                if (is == null) {
                    if (conn != null) conn.disconnect();
                    lastException = new RuntimeException("No response stream for code " + responseCode);
                    continue;
                }
                
                BufferedReader reader = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8));
                StringBuilder response = new StringBuilder();
                String line;
                while ((line = reader.readLine()) != null) {
                    response.append(line);
                }
                reader.close();
                is.close();
                conn.disconnect();
                
                if (responseCode != HttpURLConnection.HTTP_OK) {
                    AIChatController.addChatLine("API Error: " + responseCode + " - " + response.toString());
                    return null;
                }
                
                return response.toString();
            } catch (Exception e) {
                lastException = e;
                if (conn != null) {
                    try { conn.disconnect(); } catch (Exception ignored) {}
                }
                if (attempt == MAX_RETRIES - 1) {
                    AIChatController.addChatLine("API Request Error (" + MAX_RETRIES + " retries): " + e.getMessage());
                    e.printStackTrace();
                } else {
                    try { Thread.sleep(100); } catch (InterruptedException ie) { Thread.currentThread().interrupt(); break; }
                }
            }
        }
        return null;
    }
    
    /**
     * Makes a GET request to the API
     * @param endpoint The API endpoint
     * @return The response as a string, or null on error
     */
    public static String getRequest(String endpoint) {
        try {
            String urlString = BASE_URL + endpoint;
            URL url = new URL(urlString);
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            
            conn.setRequestMethod("GET");
            conn.setConnectTimeout(5000);
            conn.setReadTimeout(10000);
            
            int responseCode = conn.getResponseCode();
            InputStream is = responseCode == HttpURLConnection.HTTP_OK
                    ? conn.getInputStream()
                    : conn.getErrorStream();
            
            BufferedReader reader = new BufferedReader(
                    new InputStreamReader(is, StandardCharsets.UTF_8));
            StringBuilder response = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) {
                response.append(line);
            }
            reader.close();
            is.close();
            
            if (responseCode != HttpURLConnection.HTTP_OK) {
                AIChatController.addChatLine("API GET Error: " + responseCode + " - " + response.toString());
                return null;
            }
            
            return response.toString();
        } catch (Exception e) {
            AIChatController.addChatLine("API GET Request Error: " + e.getMessage());
            e.printStackTrace();
            return null;
        }
    }
}

