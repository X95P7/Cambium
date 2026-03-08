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
    private static final String BASE_URL = "http://backend:8000";
    
    /**
     * Makes a POST request to the API
     * @param endpoint The API endpoint (e.g., "/predict-action/v1")
     * @param jsonPayload The JSON payload to send
     * @return The response as a string, or null on error
     */
    public static String postRequest(String endpoint, String jsonPayload) {
        try {
            String urlString = BASE_URL + endpoint;
            URL url = new URL(urlString);
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setDoOutput(true);
            conn.setConnectTimeout(5000);
            conn.setReadTimeout(10000);
            
            if (jsonPayload != null) {
                OutputStream os = conn.getOutputStream();
                os.write(jsonPayload.getBytes(StandardCharsets.UTF_8));
                os.close();
            }
            
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
                AIChatController.addChatLine("API Error: " + responseCode + " - " + response.toString());
                return null;
            }
            
            return response.toString();
        } catch (Exception e) {
            AIChatController.addChatLine("API Request Error: " + e.getMessage());
            e.printStackTrace();
            return null;
        }
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

