package net.famzangl.minecraft.minebot.ai.strategy.cambium;

import java.util.ArrayList;
import java.util.LinkedList;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import net.famzangl.minecraft.minebot.ai.AIHelper;
import net.famzangl.minecraft.minebot.ai.cambiumInputs.APIClient;
import net.famzangl.minecraft.minebot.ai.cambiumInputs.ActionSpaceConfig;
import net.famzangl.minecraft.minebot.ai.cambiumInputs.ObservationSpaceConfig;
import net.famzangl.minecraft.minebot.ai.cambiumInputs.DataClasses.BlockData;
import net.famzangl.minecraft.minebot.ai.cambiumInputs.DataClasses.EntityData;
import net.famzangl.minecraft.minebot.ai.cambiumInputs.DataClasses.InventoryData;
import net.famzangl.minecraft.minebot.ai.cambiumInputs.DataClasses.PlayerData;
import net.famzangl.minecraft.minebot.ai.cambiumInputs.GetInformation.GetBlocks;
import net.famzangl.minecraft.minebot.ai.cambiumInputs.GetInformation.GetEntities;
import net.famzangl.minecraft.minebot.ai.cambiumInputs.GetInformation.GetInventory;
import net.famzangl.minecraft.minebot.ai.cambiumInputs.GetInformation.GetPlayer;
import net.famzangl.minecraft.minebot.ai.command.AIChatController;
import net.famzangl.minecraft.minebot.ai.strategy.AIStrategy;
import net.famzangl.minecraft.minebot.PhysicsController;

/**
 * RL Controller Strategy - Main event loop for reinforcement learning
 * Handles observation collection, action prediction, and execution
 */
public class RLControllerStrategy extends AIStrategy {
    
    private PhysicsController physicsController;
    private ActionSpaceConfig actionConfig;
    private ObservationSpaceConfig observationConfig;
    private String modelVersion = "v1";
    private String modelEndpoint = null;
    
    // Tick rate management
    private LinkedList<Long> tickTimes = new LinkedList<Long>();
    private static final int TICK_HISTORY_SIZE = 20;
    private static final double TICK_RATE_TARGET_PERCENTILE = 0.9;
    
    // Observation data
    private PlayerData playerData;
    private ArrayList<EntityData> entities;
    private ArrayList<BlockData> blocks;
    private ArrayList<InventoryData> inventory;
    
    // Gson for JSON parsing
    private Gson gson = new Gson();
    private JsonParser jsonParser = new JsonParser();
    
    public RLControllerStrategy() {
        this.physicsController = new PhysicsController();
        this.actionConfig = new ActionSpaceConfig();
        this.observationConfig = new ObservationSpaceConfig();
    }
    
    @Override
    public String getDescription(AIHelper helper) {
        return "RL Controller - Model: " + (modelEndpoint != null ? modelEndpoint : modelVersion);
    }
    
    @Override
    protected TickResult onGameTick(AIHelper helper) {
        try {
            // Update tick timing
            updateTickTiming();
            
            // Collect observations
            collectObservations(helper);
            
            // Get action from model
            JsonObject action = predictAction(helper);
            
            if (action != null) {
                // Execute action
                executeAction(action);
            }
            
            return TickResult.TICK_HANDLED;
        } catch (Exception e) {
            AIChatController.addChatLine("RL Controller Error: " + e.getMessage());
            e.printStackTrace();
            return TickResult.TICK_HANDLED;
        }
    }
    
    /**
     * Collects all observations based on the observation space configuration
     */
    private void collectObservations(AIHelper helper) {
        if (observationConfig.includePlayerData) {
            GetPlayer getPlayer = new GetPlayer(helper);
            playerData = getPlayer.getPlayerData();
        }
        
        if (observationConfig.includeEntityData) {
            GetEntities getEntities = new GetEntities(helper);
            entities = getEntities.getEntities();
            // Limit to maxEntities
            if (entities.size() > observationConfig.maxEntities) {
                entities = new ArrayList<EntityData>(entities.subList(0, observationConfig.maxEntities));
            }
        }
        
        if (observationConfig.includeBlockData) {
            GetBlocks getBlocks = new GetBlocks(helper);
            blocks = getBlocks.doRaytrace();
            // Limit to maxBlocks
            if (blocks != null && blocks.size() > observationConfig.maxBlocks) {
                blocks = new ArrayList<BlockData>(blocks.subList(0, observationConfig.maxBlocks));
            }
        }
        
        if (observationConfig.includeInventoryData) {
            GetInventory getInventory = new GetInventory(helper);
            inventory = getInventory.getInventoryData();
        }
    }
    
    /**
     * Builds observation JSON from collected data
     */
    private JsonObject buildObservationJson() {
        JsonObject obs = new JsonObject();
        
        if (observationConfig.includePlayerData && playerData != null) {
            JsonObject player = new JsonObject();
            if (observationConfig.includeHealth) {
                player.addProperty("health", playerData.getHealth());
            }
            if (observationConfig.includePosition) {
                player.addProperty("x", playerData.getPlayerX());
                player.addProperty("y", playerData.getPlayerY());
                player.addProperty("z", playerData.getPlayerZ());
            }
            if (observationConfig.includeRotation) {
                player.addProperty("yaw", playerData.getPlayerYaw());
                player.addProperty("pitch", playerData.getPlayerPitch());
            }
            if (observationConfig.includeArmor) {
                player.addProperty("armor", playerData.getAmror());
            }
            obs.add("player", player);
        }
        
        if (observationConfig.includeEntityData && entities != null) {
            JsonArray entityArray = new JsonArray();
            for (EntityData entity : entities) {
                JsonObject e = new JsonObject();
                e.addProperty("isProjectile", entity.isProjectile());
                e.addProperty("isPlayer", entity.isPlayer());
                e.addProperty("health", entity.getHealth());
                e.addProperty("armor", entity.getArmor());
                e.addProperty("handDamage", entity.getHandDamage());
                e.addProperty("relativeX", entity.getRelativeX());
                e.addProperty("relativeY", entity.getRelativeY());
                e.addProperty("relativeZ", entity.getRelativeZ());
                e.addProperty("veloX", entity.getVeloX());
                e.addProperty("veloY", entity.getVeloY());
                e.addProperty("veloZ", entity.getVeloZ());
                e.addProperty("facingYaw", entity.getFacingYaw());
                e.addProperty("facingPitch", entity.getFacingPitch());
                entityArray.add(e);
            }
            obs.add("entities", entityArray);
        }
        
        if (observationConfig.includeBlockData && blocks != null) {
            JsonArray blockArray = new JsonArray();
            for (BlockData block : blocks) {
                JsonObject b = new JsonObject();
                b.addProperty("x", block.getX());
                b.addProperty("y", block.getY());
                b.addProperty("z", block.getZ());
                b.addProperty("distance", block.getDistance());
                b.addProperty("solid", block.isSolid());
                b.addProperty("name", block.getName());
                blockArray.add(b);
            }
            obs.add("blocks", blockArray);
        }
        
        if (observationConfig.includeInventoryData && inventory != null) {
            JsonArray invArray = new JsonArray();
            for (InventoryData inv : inventory) {
                JsonObject i = new JsonObject();
                i.addProperty("slotNumber", inv.getSlotNumber());
                i.addProperty("count", inv.getCount());
                i.addProperty("isBlock", inv.isBlock());
                i.addProperty("isWeapon", inv.isWeapon());
                i.addProperty("weaponDamage", inv.getWeaponDamage());
                i.addProperty("isProjectile", inv.isProjectile());
                i.addProperty("flair", inv.getFlair());
                invArray.add(i);
            }
            obs.add("inventory", invArray);
        }
        
        return obs;
    }
    
    /**
     * Predicts action from the model
     */
    private JsonObject predictAction(AIHelper helper) {
        try {
            // Build observation JSON
            JsonObject observation = buildObservationJson();
            
            // Build action space config JSON
            JsonObject actionSpaceJson = new JsonObject();
            actionSpaceJson.addProperty("enableMovement", actionConfig.enableMovement);
            actionSpaceJson.addProperty("enableJump", actionConfig.enableJump);
            actionSpaceJson.addProperty("enableSneak", actionConfig.enableSneak);
            actionSpaceJson.addProperty("enableSprint", actionConfig.enableSprint);
            actionSpaceJson.addProperty("enableAttack", actionConfig.enableAttack);
            actionSpaceJson.addProperty("enableUseItem", actionConfig.enableUseItem);
            actionSpaceJson.addProperty("enableHotbar", actionConfig.enableHotbar);
            actionSpaceJson.addProperty("enableLook", actionConfig.enableLook);
            actionSpaceJson.addProperty("movementBins", actionConfig.movementBins);
            actionSpaceJson.addProperty("yawBins", actionConfig.yawBins);
            actionSpaceJson.addProperty("pitchBins", actionConfig.pitchBins);
            
            // Get bot name
            String botName = helper.getMinecraft().thePlayer != null 
                    ? helper.getMinecraft().thePlayer.getName() 
                    : "unknown";
            
            // Build request JSON
            JsonObject request = new JsonObject();
            request.add("observation", observation);
            request.add("action_space", actionSpaceJson);
            request.addProperty("bot_name", botName);
            
            // Determine endpoint
            String endpoint = modelEndpoint != null 
                    ? "/predict-action/" + modelEndpoint
                    : "/predict-action/" + modelVersion;
            
            // Make API call
            String response = APIClient.postRequest(endpoint, request.toString());
            
            if (response != null) {
                JsonObject responseJson = jsonParser.parse(response).getAsJsonObject();
                
                // Update tick rate if provided
                if (responseJson.has("tick_rate")) {
                    double tickRate = responseJson.get("tick_rate").getAsDouble();
                    updateTickRate(tickRate);
                }
                
                // Return action
                if (responseJson.has("action")) {
                    return responseJson.getAsJsonObject("action");
                }
            }
        } catch (Exception e) {
            AIChatController.addChatLine("Predict Action Error: " + e.getMessage());
            e.printStackTrace();
        }
        
        return null;
    }
    
    /**
     * Executes the predicted action
     */
    private void executeAction(JsonObject action) {
        // Reset all controls
        physicsController.forward = false;
        physicsController.back = false;
        physicsController.left = false;
        physicsController.right = false;
        physicsController.jump = false;
        physicsController.sneak = false;
        physicsController.sprint = false;
        physicsController.attack = false;
        physicsController.useItem = false;
        physicsController.deltaYaw = 0f;
        physicsController.deltaPitch = 0f;
        
        // Apply movement
        if (action.has("movement")) {
            int movement = action.get("movement").getAsInt();
            applyMovement(movement);
        }
        
        // Apply jump
        if (action.has("jump")) {
            physicsController.jump = action.get("jump").getAsBoolean();
        }
        
        // Apply sneak
        if (action.has("sneak")) {
            physicsController.sneak = action.get("sneak").getAsBoolean();
        }
        
        // Apply sprint
        if (action.has("sprint")) {
            physicsController.sprint = action.get("sprint").getAsBoolean();
        }
        
        // Apply attack
        if (action.has("attack")) {
            physicsController.attack = action.get("attack").getAsBoolean();
        }
        
        // Apply use item
        if (action.has("useItem")) {
            physicsController.useItem = action.get("useItem").getAsBoolean();
        }
        
        // Apply hotbar selection
        if (action.has("hotbar")) {
            int hotbarSlot = action.get("hotbar").getAsInt();
            applyHotbar(hotbarSlot);
        }
        
        // Apply look
        if (action.has("yaw")) {
            physicsController.deltaYaw = action.get("yaw").getAsFloat();
        }
        if (action.has("pitch")) {
            physicsController.deltaPitch = action.get("pitch").getAsFloat();
        }
        
        // Apply physics
        physicsController.tick();
    }
    
    /**
     * Applies movement based on movement bin
     */
    private void applyMovement(int movementBin) {
        // 8 directions: 0=N, 1=NE, 2=E, 3=SE, 4=S, 5=SW, 6=W, 7=NW
        switch (movementBin) {
            case 0: // North
                physicsController.forward = true;
                break;
            case 1: // Northeast
                physicsController.forward = true;
                physicsController.right = true;
                break;
            case 2: // East
                physicsController.right = true;
                break;
            case 3: // Southeast
                physicsController.back = true;
                physicsController.right = true;
                break;
            case 4: // South
                physicsController.back = true;
                break;
            case 5: // Southwest
                physicsController.back = true;
                physicsController.left = true;
                break;
            case 6: // West
                physicsController.left = true;
                break;
            case 7: // Northwest
                physicsController.forward = true;
                physicsController.left = true;
                break;
        }
    }
    
    /**
     * Applies hotbar selection
     */
    private void applyHotbar(int slot) {
        if (slot >= 0 && slot <= 9) {
            switch (slot) {
                case 0: physicsController.hotbar0 = true; break;
                case 1: physicsController.hotbar1 = true; break;
                case 2: physicsController.hotbar2 = true; break;
                case 3: physicsController.hotbar3 = true; break;
                case 4: physicsController.hotbar4 = true; break;
                case 5: physicsController.hotbar5 = true; break;
                case 6: physicsController.hotbar6 = true; break;
                case 7: physicsController.hotbar7 = true; break;
                case 8: physicsController.hotbar8 = true; break;
                case 9: physicsController.hotbar9 = true; break;
            }
        }
    }
    
    /**
     * Updates tick timing and calculates tick rate
     */
    private void updateTickTiming() {
        long currentTime = System.currentTimeMillis();
        tickTimes.add(currentTime);
        
        if (tickTimes.size() > TICK_HISTORY_SIZE) {
            tickTimes.removeFirst();
        }
    }
    
    /**
     * Updates tick rate based on 90th percentile of past 20 ticks
     */
    private void updateTickRate(double targetTickRate) {
        if (tickTimes.size() < 2) return;
        
        // Calculate tick intervals
        ArrayList<Long> intervals = new ArrayList<Long>();
        for (int i = 1; i < tickTimes.size(); i++) {
            intervals.add(tickTimes.get(i) - tickTimes.get(i - 1));
        }
        
        // Sort intervals
        intervals.sort(null);
        
        // Get 90th percentile
        int percentileIndex = (int) (intervals.size() * TICK_RATE_TARGET_PERCENTILE);
        if (percentileIndex >= intervals.size()) {
            percentileIndex = intervals.size() - 1;
        }
        
        long percentileInterval = intervals.get(percentileIndex);
        double currentTickRate = 1000.0 / percentileInterval;
        
        // Calculate desired tick rate (90% of target)
        double desiredTickRate = targetTickRate * 0.9;
        
        // Adjust tick rate if needed (this would require server-side command)
        // For now, we just track it
    }
    
    /**
     * Sets the action space configuration
     */
    public void setActionSpaceConfig(ActionSpaceConfig config) {
        this.actionConfig = config;
    }
    
    /**
     * Sets the observation space configuration
     */
    public void setObservationSpaceConfig(ObservationSpaceConfig config) {
        this.observationConfig = config;
    }
    
    /**
     * Sets the model version/endpoint
     */
    public void setModelEndpoint(String endpoint) {
        this.modelEndpoint = endpoint;
    }
    
    /**
     * Loads action space configuration from API
     */
    public void loadActionSpaceConfig() {
        String response = APIClient.getRequest("/set-action-space");
        if (response != null) {
            try {
                JsonObject configJson = jsonParser.parse(response).getAsJsonObject();
                actionConfig.enableMovement = configJson.get("enableMovement").getAsBoolean();
                actionConfig.enableJump = configJson.get("enableJump").getAsBoolean();
                actionConfig.enableSneak = configJson.get("enableSneak").getAsBoolean();
                actionConfig.enableSprint = configJson.get("enableSprint").getAsBoolean();
                actionConfig.enableAttack = configJson.get("enableAttack").getAsBoolean();
                actionConfig.enableUseItem = configJson.get("enableUseItem").getAsBoolean();
                actionConfig.enableHotbar = configJson.get("enableHotbar").getAsBoolean();
                actionConfig.enableLook = configJson.get("enableLook").getAsBoolean();
                if (configJson.has("movementBins")) {
                    actionConfig.movementBins = configJson.get("movementBins").getAsInt();
                }
                if (configJson.has("yawBins")) {
                    actionConfig.yawBins = configJson.get("yawBins").getAsInt();
                }
                if (configJson.has("pitchBins")) {
                    actionConfig.pitchBins = configJson.get("pitchBins").getAsInt();
                }
            } catch (Exception e) {
                AIChatController.addChatLine("Error loading action space config: " + e.getMessage());
            }
        }
    }
    
    /**
     * Loads observation space configuration from API
     */
    public void loadObservationSpaceConfig() {
        String response = APIClient.getRequest("/set-observation-space");
        if (response != null) {
            try {
                JsonObject configJson = jsonParser.parse(response).getAsJsonObject();
                observationConfig.includePlayerData = configJson.get("includePlayerData").getAsBoolean();
                observationConfig.includeEntityData = configJson.get("includeEntityData").getAsBoolean();
                observationConfig.includeBlockData = configJson.get("includeBlockData").getAsBoolean();
                observationConfig.includeInventoryData = configJson.get("includeInventoryData").getAsBoolean();
                if (configJson.has("maxEntities")) {
                    observationConfig.maxEntities = configJson.get("maxEntities").getAsInt();
                }
                if (configJson.has("maxBlocks")) {
                    observationConfig.maxBlocks = configJson.get("maxBlocks").getAsInt();
                }
                if (configJson.has("maxInventorySlots")) {
                    observationConfig.maxInventorySlots = configJson.get("maxInventorySlots").getAsInt();
                }
            } catch (Exception e) {
                AIChatController.addChatLine("Error loading observation space config: " + e.getMessage());
            }
        }
    }
    
    /**
     * Loads model endpoint from API
     */
    public void loadModelEndpoint() {
        String response = APIClient.getRequest("/set-model");
        if (response != null) {
            try {
                JsonObject modelJson = jsonParser.parse(response).getAsJsonObject();
                if (modelJson.has("endpoint")) {
                    modelEndpoint = modelJson.get("endpoint").getAsString();
                } else if (modelJson.has("version")) {
                    modelVersion = modelJson.get("version").getAsString();
                }
            } catch (Exception e) {
                AIChatController.addChatLine("Error loading model endpoint: " + e.getMessage());
            }
        }
    }
    
    /**
     * Sends reward/event information to the API
     * @param helper AIHelper to get player name
     * @param events List of events (damage_dealt, damage_taken, good_aim, etc.)
     */
    private void sendRewardEvents(AIHelper helper, JsonArray events) {
        try {
            String botName = helper.getMinecraft().thePlayer != null 
                    ? helper.getMinecraft().thePlayer.getName() 
                    : "unknown";
            
            // Build current state from observations
            JsonObject currentState = buildObservationJson();
            
            // Build request JSON
            JsonObject request = new JsonObject();
            request.addProperty("bot_name", botName);
            request.add("events", events);
            request.add("current_state", currentState);
            
            // Send to API
            APIClient.postRequest("/add-reward/", request.toString());
        } catch (Exception e) {
            // Silently fail - reward tracking is not critical
            e.printStackTrace();
        }
    }
}

