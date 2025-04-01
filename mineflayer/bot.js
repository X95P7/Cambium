const mineflayer = require('mineflayer')
const { mineflayer: mineflayerViewer } = require('prismarine-viewer')
const fs = require('fs')
const path = require('path')
const puppeteer = require('puppeteer')
const FormData = require('form-data')
const axios = require('axios')
// Create bot instance
const bot = mineflayer.createBot({
  host: process.argv[2] ||  'localhost',
  port: 25565,
  username: process.argv[3] || 'Bot1',
  // auth: 'microsoft' // Uncomment for premium accounts
})


// Directory to save screenshots
const screenshotsDir = path.join(__dirname, 'screenshots')
if (!fs.existsSync(screenshotsDir)) {
  fs.mkdirSync(screenshotsDir)
}

// Python server endpoint where images will be sent
const PYTHON_SERVER_URL = 'http://localhost:5000/receive_image'

let browser = null
let page = null
let viewerReady = false

// Start Prismarine Viewer when bot spawns
bot.once('spawn', async () => {
  console.log('Bot spawned')
  
  // Start the viewer
  mineflayerViewer(bot, { port: 3000, firstPerson: true })
  
  // Initialize Puppeteer for capturing the actual viewer
  try {
    browser = await puppeteer.launch({ 
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    })
    page = await browser.newPage()
    await page.setViewport({ width: 800, height: 600 })
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle0' })
    
    console.log('Puppeteer initialized and connected to viewer')
    
    // Set a delay to ensure the viewer is fully loaded
    setTimeout(() => {
      viewerReady = true
      console.log('Viewer ready, capturing will begin soon...')
      
      // Start capturing images at regular intervals
      startCapturing()
    }, 5000)
  } catch (error) {
    console.error('Error initializing Puppeteer:', error)
  }
})

// Handle errors
bot.on('error', (err) => {
  console.error('Error:', err)
})

// Capture the current view from Prismarine Viewer
async function captureViewerImage() {
  if (!viewerReady || !page) {
    console.log('Viewer or Puppeteer not ready yet')
    return null
  }
  
  try {
    // Wait for the canvas to be rendered
    await page.waitForSelector('canvas')
    
    // Take a screenshot of the canvas
    const screenshot = await page.screenshot({
      type: 'png',
      omitBackground: true
    })
    
    console.log(`Captured screenshot (${screenshot.length} bytes)`)
    return screenshot
  } catch (error) {
    console.error('Error capturing image:', error)
    return null
  }
}

// Save the captured image to disk
function saveImage(imageBuffer, filename) {
  if (!imageBuffer) return false
  
  const filepath = path.join(screenshotsDir, filename)
  fs.writeFileSync(filepath, imageBuffer)
  console.log(`Saved image to ${filepath}`)
  return filepath
}

// Send image to Python server
async function sendImageToPython(imageBuffer, metadata = {}) {
  if (!imageBuffer) return false
  
  try {
    // Create form data with the image and metadata
    const formData = new FormData()
formData.append('image', Buffer.from(imageBuffer), {
  filename: 'screenshot.png',
  contentType: 'image/png'
})
    
    // Add bot state information as metadata
    const botData = {
      position: {
        x: bot.entity.position.x,
        y: bot.entity.position.y,
        z: bot.entity.position.z
      },
      health: bot.health,
      food: bot.food,
      inventory: bot.inventory.items().map(item => ({
        name: item.name,
        count: item.count
      })),
      ...metadata
    }
    
    formData.append('metadata', JSON.stringify(botData))
    
    // Send to Python server with verbose logging
    console.log(`Sending image to Python server at ${PYTHON_SERVER_URL}...`)
    const response = await axios.post(PYTHON_SERVER_URL, formData, {
      headers: formData.getHeaders()
    })
    
    console.log('Response from Python server:', response.data)
    return true
  } catch (error) {
    console.error('Error sending image to Python server:', error)
    console.error('Error details:', error.message)
    if (error.response) {
      console.error('Response status:', error.response.status)
      console.error('Response data:', error.response.data)
    }
    return false
  }
}

// Start capturing images at regular intervals
function startCapturing(intervalMs = 50) {
  console.log(`Starting image capture every ${intervalMs}ms`)
  
  setInterval(async () => {
    const imageBuffer = await captureViewerImage()
    if (imageBuffer) {
      // Save locally (optional)
      const timestamp = Date.now()
      const filename = `screenshot_${timestamp}.png`
      saveImage(imageBuffer, filename)
      
      // Send to Python server
      const success = await sendImageToPython(imageBuffer, {
        timestamp,
        gameTime: bot.time.timeOfDay
      })
      
      if (success) {
        console.log('Successfully sent image to Python server')
      } else {
        console.log('Failed to send image to Python server')
      }
    }
  }, intervalMs)
}

// Listen for Python commands
const express = require('express')
const bodyParser = require('body-parser')
const app = express()
app.use(bodyParser.json())

app.post('/command', (req, res) => {
  const { action, params } = req.body
  console.log(`Received command: ${action}`, params)
  
  // Handle different actions from the Python RL algorithm
  switch(action) {
    case 'move':
      bot.setControlState('forward', params.forward)
      bot.setControlState('back', params.back)
      bot.setControlState('left', params.left)
      bot.setControlState('right', params.right)
      bot.setControlState('jump', params.jump)
      break
    case 'look':
      bot.look(params.yaw, params.pitch)
      break
    default:
      console.log('Unknown action:', action)
  }
  
  res.json({ 
    status: 'success', 
    botPos: {
      x: bot.entity.position.x,
      y: bot.entity.position.y,
      z: bot.entity.position.z
    }
  })
})

// Start the command server
const PORT = 3001
app.listen(PORT, () => {
  console.log(`Command server listening on port ${PORT}`)
})

// Cleanup on exit
process.on('SIGINT', async () => {
  console.log('Shutting down...')
  if (browser) {
    await browser.close()
  }
  process.exit()
})