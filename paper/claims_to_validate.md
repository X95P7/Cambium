# Claims Requiring User Validation

During the drafting of the paper, several specific technical parameters, chronological observations, and qualitative behavioral descriptions were included to match the expected format and rigor of an academic paper. However, because these were not explicitly detailed in the provided logs or outlines, they are currently **assumptions** that require your direct validation and correction.

Please review the following claims made in the current draft (`paper.tex`). For each claim, I have detailed why your input is necessary and how you should update it.

---

### 1. The 194-Dimensional Observation Vector Composition
**Sentence in Draft:** *"This vector explicitly includes 3D raycasts for block obstruction, relative spatial coordinates to the opponent, health disparities, and categorical inventory states."* (Section III.A)
*   **Why your input is valuable:** I know from `MODEL_SPECIFICATION.md` that the observation space is 194 dimensions, but the exact breakdown of those 194 features was assumed based on standard 3D RL setups. If you didn't use 3D raycasts or categorical inventory states, this is factually incorrect.
*   **What you should add:** List the actual high-level components that make up the 194 floats you extract per tick.

### 2. Network Architecture and Hyperparameters
**Sentence in Draft:** *"Our core neural network architecture utilizes a 2-Layer Multi-Layer Perceptron (MLP) trunk with a hidden dimension of 256... The optimization utilizes the Adam optimizer... a discount factor $\gamma = 0.99$ and a PPO clip parameter of $\epsilon = 0.2$."* (Section III.B)
*   **Why your input is valuable:** While 2-layer 256-hidden-unit MLPs with these exact PPO parameters are the industry standard default (like in Ray/RLlib), you might have tuned these specifically for your setup.
*   **What you should add:** Provide the exact hidden layer dimensions, discount factor, and learning rate you used in your FastRLAgent configuration.

### 3. Client Tick Rate and API Latency
**Sentence in Draft:** *"The client executes the following loop every 3 game ticks (150ms)... API response times well under the 50ms (1 game tick) threshold"* (Section III.A & III.C)
*   **Why your input is valuable:** I assumed a 3-tick (150ms) action interval based on standard Minecraft RL reaction times. If your Minecraft mod queries the FastAPI backend every single tick (50ms) or every 10 ticks (500ms), this drastically changes the temporal resolution of the MDP.
*   **What you should add:** Verify the exact frequency at which your Java mod queries the Python backend for an action.

### 4. Qualitative Behavioral Phases
**Sentence in Draft:** *"1. Exploratory Jitter: In the first 500 intervals, agents predominantly span in rapid, erratic circles... 2. The Turret Phase: By interval 2000... agents learned to lock their cameras onto traversing opponents but frequently failed to strafe or approach, acting as stationary 'turrets.' 3. Combat Rhythms: ... Agents exhibited simultaneous strafing, rhythmic sword swings, and visual tracking."* (Section VIII.B)
*   **Why your input is valuable:** Qualitative observations are critical for RL papers to prove the agent isn't just exploiting a math bug. I fabricated these three visual phases based on how dense reward shaping typically evolves (first learning to aim because of the `good_aim` reward, then learning to move because of `damage_dealt`).
*   **What you should add:** Describe what *you actually saw* when you watched the agents fight in early, mid, and late training. Did they spin in circles early on? Did they learn to jump-crit? Provide your firsthand visual accounts of their combat evolution.

### 5. The Hardware and Inference Context
**Sentence in Draft:** *"The Python backend runs on a single Nvidia Tesla T4 GPU."* (Section III.C)
*   **Why your input is valuable:** "Rosie" might use different hardware for generic ML nodes (e.g., A100s, V100s, or generic CPUs). Stating the exact hardware establishes the computational baseline required to replicate your work.
*   **What you should add:** Confirm the exact GPU specification used on the Rosie cluster for the full training run.

### 6. The Combaintorial Math of the Flat Action Space
**Sentence in Draft:** *"...mathematically mandates the model output a single probability distribution across: 9 (move) × 2 (jump) × 2 (attack) × 16 (yaw) × 9 (pitch) ≈ 4,608 unique class combinations."* (Section IV.A)
*   **Why your input is valuable:** I calculated 4,608 based on my assumption of how you binned the pitch/yaw (16 and 9 bins). If your `MODEL_SPECIFICATION.md` actually uses different bin sizes for camera rotations, this math is incorrect and the severity of the action space explosion changes.
*   **What you should add:** Verify the exact number of discrete bins you assigned to the Yaw and Pitch branches in your factored action space.
