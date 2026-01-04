package net.famzangl.minecraft.minebot.ai.cambiumInputs;

import java.util.ArrayList;
import java.util.List;

/**
 * Configuration for the observation space - defines what observations the bot can make
 */
public class ObservationSpaceConfig {
    public boolean includePlayerData = true;
    public boolean includeEntityData = true;
    public boolean includeBlockData = true;
    public boolean includeInventoryData = true;
    
    // Limits on data collection
    public int maxEntities = 10;
    public int maxBlocks = 50;
    public int maxInventorySlots = 36;
    
    // Feature flags for specific observations
    public boolean includeHealth = true;
    public boolean includePosition = true;
    public boolean includeRotation = true;
    public boolean includeVelocity = true;
    public boolean includeArmor = true;
    
    // Observation types that are enabled
    public List<String> enabledObservations = new ArrayList<String>();
    
    public ObservationSpaceConfig() {
        // Default enabled observations
        enabledObservations.add("player");
        enabledObservations.add("entities");
        enabledObservations.add("blocks");
        enabledObservations.add("inventory");
    }
    
    /**
     * Get the total observation space size
     */
    public int getObservationSpaceSize() {
        int size = 0;
        if (includePlayerData) {
            if (includeHealth) size += 1;
            if (includePosition) size += 3;
            if (includeRotation) size += 2;
            if (includeVelocity) size += 3;
            if (includeArmor) size += 1;
        }
        if (includeEntityData) {
            size += maxEntities * 15; // 15 features per entity
        }
        if (includeBlockData) {
            size += maxBlocks * 6; // 6 features per block
        }
        if (includeInventoryData) {
            size += maxInventorySlots * 7; // 7 features per inventory slot
        }
        return size;
    }
}

