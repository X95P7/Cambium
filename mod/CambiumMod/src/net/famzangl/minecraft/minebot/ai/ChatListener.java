package net.famzangl.minecraft.minebot.ai;

import net.famzangl.minecraft.minebot.ai.strategy.cambium.LeftClickStrategy;
import net.minecraftforge.client.event.ClientChatReceivedEvent;
import net.minecraftforge.fml.common.eventhandler.SubscribeEvent;

public class ChatListener {
    @SubscribeEvent
    public void onChatReceived(ClientChatReceivedEvent event) {
        // Get the message as a string
        String message = event.message.getUnformattedText();

        // Check if the message contains the target phrase
        if (message.contains("&setup")) {
            System.out.println("Detected 'setup' in chat!");
            AIController controller = AIController.getInstance();
            controller.addStrategy(new LeftClickStrategy(15, 20, controller.getAiHelper()));

            // Optional: Cancel the message from appearing in chat
            // event.setCanceled(true);
        }
    }
}
