

/*******************************************************************************
    _______      ____    ,---.    ,---. _______  .-./`)   ___    _ ,---.    ,---.        
   /   __  \   .'  __ `. |    \  /    |\  ____  \\ .-.').'   |  | ||    \  /    |        
  | ._/  \__) /   '  \  \|  ,  \/  ,  || |    \ |/ `-' \|   .|  | ||  ,  \/  ,  |        
,-./  )       |___|  /  ||  |\_   /|  || |____/ / `-'`"`.'  'L  | ||  |\_   /|  |        
\  '_ '`)        _.-`   ||  _( )_/ |  ||   _ _ '. .---. '   ( \.-.||  _( )_/ |  |        
 > (_)  )  __ .'   _    || (_ o _) |  ||  ( ' )  \|   | ' (`. _` /|| (_ o _) |  |        
(  .  .-'_/  )|  _( )_  ||  (_,_)  |  || (_{;}_) ||   | | (_ (_) _)|  (_,_)  |  |        
 `-'`-'     / \ (_ o _) /|  |      |  ||  (_,_)  /|   |  \ /  . \ /|  |      |  |        
   `\_____.'   '.(_,_).' '--'      '--'/_______.' '---'   ``-'`-'' '--'      '--'        
                                                                                         
 *******************************************************************************/

/**
 * This is a first version controller. It has very simplified and curated inputs and outputs.
 * These can be changed as needed to accomidate additional skills and tasks.
 * Think of this as more of a playground then something rigid, if you wnat to change somehting do it here.
 * Update getters as nessicary, just make sure changes all fully intigrated 
 * Work with this in a way that won't lead it to break later.
 */




package net.famzangl.minecraft.minebot.ai.strategy.cambium;

import java.lang.reflect.Array;
import java.util.ArrayList;

import net.famzangl.minecraft.minebot.ai.AIHelper;
import net.famzangl.minecraft.minebot.ai.cambiumInputs.DataClasses.BlockData;
import net.famzangl.minecraft.minebot.ai.cambiumInputs.DataClasses.EntityData;
import net.famzangl.minecraft.minebot.ai.cambiumInputs.GetInformation.GetBlocks;
import net.famzangl.minecraft.minebot.ai.cambiumInputs.GetInformation.GetEntities;
import net.famzangl.minecraft.minebot.ai.command.AIChatController;
import net.famzangl.minecraft.minebot.ai.strategy.AIStrategy;
import net.famzangl.minecraft.minebot.ai.cambiumInputs.*;

//client
import net.minecraft.client.settings.GameSettings;
import net.minecraft.client.settings.KeyBinding;

/**
 * Makes API calls using current game data, recives back a response and acts on it using AIHelper and task
 * 
 * @author Xylim
 *
 */
public class cambiumController extends AIStrategy {
  //setup output varibles  
  //Left Click
  private int leftClickTicks;
  private int leftClickMaxTicks;
  private double leftClickOften;
  //Right Click
  private int rightClickTicks;
  private int rightClickMaxTicks;
  private double rightClickOften;
  //Movement
  private boolean jump;
  private double x;
  private double z;

  //Observations
  private ArrayList<BlockData> blocks;
  // invertory private ArrayList<invetoryData> blocks;
  //entity private ArrayList<entityData> blocks;

    //swpainvetory is inline
    //setHotbar is inline
    //yaw and pitch are inline

    public String getDescription(AIHelper helper) {
		return "Controls All!" + getClass().getSimpleName();
	}

    @Override
	protected TickResult onGameTick(AIHelper helper) {
        //get RNN inputs
        //send inputs to RNN
        //get RNN outputs
        //use outputs to control player
        return TickResult.TICK_HANDLED;
	}

  private ArrayList<BlockData> getBlocks(AIHelper helper){
    //get blocks
    return new GetBlocks(helper).doRaytrace();
  }

  private ArrayList<EntityData> getEntities(AIHelper helper){
    //get entities
    return new GetEntities(helper).getEntities();
  }


}


        

