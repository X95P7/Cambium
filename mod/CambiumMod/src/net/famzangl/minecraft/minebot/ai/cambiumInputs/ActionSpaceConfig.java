package net.famzangl.minecraft.minebot.ai.cambiumInputs;

import java.util.ArrayList;
import java.util.List;

/**
 * Configuration for the action space - defines what actions the bot can take
 */
public class ActionSpaceConfig {
    public boolean enableMovement = true;
    public boolean enableJump = true;
    public boolean enableSneak = false;
    public boolean enableSprint = false;
    public boolean enableAttack = true;
    public boolean enableUseItem = true;
    public boolean enableHotbar = true;
    public boolean enableLook = true;
    
    // Movement discretization
    public int movementBins = 8; // 8 directions (N, NE, E, SE, S, SW, W, NW)
    
    // Look discretization
    public int yawBins = 16; // 16 yaw angles
    public int pitchBins = 9; // 9 pitch angles (-90 to 90)
    
    // Action types that are enabled
    public List<String> enabledActions = new ArrayList<String>();
    
    public ActionSpaceConfig() {
        // Default enabled actions
        enabledActions.add("movement");
        enabledActions.add("jump");
        enabledActions.add("attack");
        enabledActions.add("useItem");
        enabledActions.add("hotbar");
        enabledActions.add("look");
    }
    
    /**
     * Get the total action space size
     */
    public int getActionSpaceSize() {
        int size = 0;
        if (enableMovement) size += movementBins;
        if (enableJump) size += 1;
        if (enableSneak) size += 1;
        if (enableSprint) size += 1;
        if (enableAttack) size += 1;
        if (enableUseItem) size += 1;
        if (enableHotbar) size += 10; // 0-9
        if (enableLook) size += yawBins + pitchBins;
        return size;
    }
}

